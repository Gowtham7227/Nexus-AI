import os
import re
import math
import time
import threading
from typing import List, Dict, Any, Tuple, Optional

from vector_store import get_vector_store, embedding_model
from bm25_retriever import get_or_build_bm25_index
from privacy_scanner import PrivacyScanner, PromptInjectionShield, OutputPrivacyGuard
from audit_logger import log_privacy_event


# ============================================================
# CONFIGURATION
# ============================================================

RAG_SEMANTIC_WEIGHT = float(os.getenv("RAG_SEMANTIC_WEIGHT", "0.6"))
RAG_LEXICAL_WEIGHT = float(os.getenv("RAG_LEXICAL_WEIGHT", "0.4"))

RAG_INITIAL_K = int(os.getenv("RAG_INITIAL_K", "30"))
RAG_FINAL_K = int(os.getenv("RAG_FINAL_K", "8"))
RAG_COMPARISON_K = int(os.getenv("RAG_COMPARISON_K", "6"))

RAG_RERANKER_ENABLED = os.getenv("RAG_RERANKER_ENABLED", "true").lower() in ("true", "1", "yes")
RAG_RERANKER_MODEL = os.getenv("RAG_RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
RAG_RERANKER_CROSS_ENCODER_WEIGHT = float(os.getenv("RAG_RERANKER_CROSS_ENCODER_WEIGHT", "0.7"))
RAG_RERANKER_HYBRID_WEIGHT = float(os.getenv("RAG_RERANKER_HYBRID_WEIGHT", "0.3"))

RAG_COMPRESSION_ENABLED = os.getenv("RAG_COMPRESSION_ENABLED", "true").lower() in ("true", "1", "yes")
RAG_QUERY_EXPANSION_ENABLED = os.getenv("RAG_QUERY_EXPANSION_ENABLED", "true").lower() in ("true", "1", "yes")


# ============================================================
# 1. QUERY UNDERSTANDING
# ============================================================

class QueryUnderstanding:
    """Classifies user intent, question type, point count requests, and numerical targets."""

    @staticmethod
    def analyze(question: str) -> Dict[str, Any]:
        q = question.strip().lower()
        
        # 1. Detect explicit requested point count
        count = None
        count_match = re.search(r"\b(?:in|with|give|provide|list|summarize)\s+(\d{1,2})\s+(?:points?|bullets?|items?)\b", q)
        if count_match:
            count = int(count_match.group(1))

        # 2. Detect question type
        if any(w in q for w in ("compare", "comparison", "difference", "differences", "similarity", "similarities", "versus", " vs ")):
            qtype = "comparison"
        elif any(q.startswith(w) for w in ("why ", "how ", "reason for", "purpose of", "how does", "how did")):
            qtype = "why_how"
        elif any(w in q for w in ("what is this document", "what is the document about", "tell me about this", "describe this document", "explain the document", "summary", "summarize", "overview")):
            qtype = "overview"
        elif any(q.startswith(w) for w in ("what is ", "what are ", "define ", "meaning of ", "definition of")):
            qtype = "definition"
        elif any(w in q for w in ("how many", "how much", "calculate", "total", "percentage", "rate", "cost", "revenue", "count", "number of")):
            qtype = "calculation"
        elif any(w in q for w in ("list", "key points", "bullet points", "steps", "factors", "features")):
            qtype = "list_points"
        else:
            qtype = "factual"

        return {
            "question_type": qtype,
            "requested_count": count,
            "is_calculation": qtype == "calculation",
            "is_comparison": qtype == "comparison",
            "is_overview": qtype == "overview",
            "is_definition": qtype == "definition",
        }


# ============================================================
# 2. QUERY REWRITING & EXPANSION
# ============================================================

class QueryExpander:
    """Generates targeted retrieval query variants without modifying original user intent."""

    @staticmethod
    def expand(question: str, query_info: Dict[str, Any]) -> List[str]:
        if not RAG_QUERY_EXPANSION_ENABLED:
            return [question]

        q = question.strip()
        q_lower = q.lower()
        qtype = query_info.get("question_type", "factual")

        queries = [q]

        # Extract primary entity keywords
        words = re.findall(r"[A-Za-z0-9_]+", q_lower)
        stopwords = {"what", "is", "are", "the", "a", "an", "of", "to", "for", "in", "on", "with", "and", "or", "tell", "me", "about", "explain", "please"}
        keywords = [w for w in words if w not in stopwords and len(w) >= 2]
        keyword_str = " ".join(keywords)

        if keyword_str and keyword_str != q_lower:
            queries.append(keyword_str)

        if qtype == "overview":
            queries.extend([
                "main purpose objective summary",
                "executive summary overview conclusion",
                "key topics important findings",
            ])
        elif qtype == "comparison":
            queries.extend([
                "document main topic and findings",
                "similarities and common points",
                "differences and comparative analysis",
            ])
        elif qtype == "calculation":
            queries.append(f"{keyword_str} total amount number statistics")
        elif qtype == "why_how":
            queries.append(f"{keyword_str} reason methodology approach mechanism")

        # Deduplicate while preserving order
        unique_queries = []
        for query_item in queries:
            if query_item and query_item not in unique_queries:
                unique_queries.append(query_item)

        return unique_queries[:4]


# ============================================================
# 3. LAZY SINGLETON CROSS-ENCODER RERANKER
# ============================================================

_cross_encoder_model = None
_cross_encoder_lock = threading.Lock()
_cross_encoder_failed = False


def get_cross_encoder():
    """
    Thread-safe lazy-loaded singleton for local Transformer Cross-Encoder reranker.
    Returns loaded CrossEncoder or None on failure.
    """
    global _cross_encoder_model, _cross_encoder_failed

    if _cross_encoder_model is not None:
        return _cross_encoder_model

    if _cross_encoder_failed:
        return None

    with _cross_encoder_lock:
        if _cross_encoder_model is not None:
            return _cross_encoder_model
        if _cross_encoder_failed:
            return None

        try:
            print("=" * 70)
            print("🔹 Loading Local Transformer Cross-Encoder Reranker...")
            print(f"Model: {RAG_RERANKER_MODEL}")
            print("=" * 70)
            from sentence_transformers import CrossEncoder
            _cross_encoder_model = CrossEncoder(RAG_RERANKER_MODEL)
            print("✅ Local Cross-Encoder loaded and ready")
            return _cross_encoder_model
        except Exception as ce_err:
            _cross_encoder_failed = True
            print(f"⚠️ Cross-Encoder model loading failed: {ce_err}")
            print("⚠️ Falling back to local cosine/embedding reranker.")
            return None


def sigmoid(x: float) -> float:
    """Stable sigmoid function to map Cross-Encoder logits to [0.0, 1.0]."""
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    else:
        z = math.exp(x)
        return z / (1.0 + z)


# ============================================================
# 4. ADVANCED HYBRID RETRIEVER & RERANKER
# ============================================================

class NexusAdvancedRAG:
    """
    Privacy-Aware Advanced RAG Engine:
    - Authorization & Ownership Gateway (Strict User Isolation)
    - Semantic Chroma Vector Search
    - Lexical BM25 Okapi Keyword Search
    - Hybrid Candidate Fusion (Weighted Linear Combination)
    - TRUE Local Transformer Cross-Encoder Reranking with Cosine Fallback
    - Global Multi-Document Reranking
    - Contextual Window Expansion & Sentence Compression
    - Prompt Injection Shield with XML Isolation
    - Evidence Quality Metric
    """

    @classmethod
    def get_document_chunks(cls, filename: str, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch all indexed chunks for an authorized document from Chroma."""
        vector_store = get_vector_store()
        try:
            if user_id is not None:
                where_filter = {"$and": [{"filename": filename}, {"user_id": str(user_id)}]}
            else:
                where_filter = {"filename": filename}

            results = vector_store._collection.get(
                where=where_filter,
                include=["documents", "metadatas"],
            )
            docs = results.get("documents", [])
            metas = results.get("metadatas", [])
            ids = results.get("ids", [])

            chunks = []
            for i in range(len(docs)):
                meta = metas[i] if i < len(metas) else {}
                chunk_idx = meta.get("chunk_index", i)
                page_num = meta.get("page_number", 1)
                ext_method = meta.get("extraction_method", "native")
                chunks.append({
                    "id": ids[i] if i < len(ids) else f"{filename}::{chunk_idx}",
                    "text": docs[i],
                    "filename": filename,
                    "chunk_index": chunk_idx,
                    "page_number": page_num,
                    "extraction_method": ext_method,
                    "metadata": meta,
                })

            chunks.sort(key=lambda x: x["chunk_index"])
            return chunks
        except Exception as e:
            print(f"⚠️ Error retrieving chunks for {filename}:", str(e))
            return []

    @classmethod
    def retrieve_hybrid_context(
        cls,
        question: str,
        filenames: List[str],
        user_id: int,
    ) -> Dict[str, Any]:
        """
        Execute full Privacy-Aware Advanced RAG retrieval across authorized documents.
        Security Order:
        1. User Authorization & Ownership Gate (Pre-retrieval)
        2. Multi-Query Hybrid Retrieval (Chroma + BM25)
        3. Global Candidate Pool Aggregation
        4. TRUE Transformer Cross-Encoder Reranker
        5. Contextual Expansion & Sentence Compression
        6. Prompt Injection Shield & Untrusted Data XML Isolation
        """
        t_start = time.time()
        if not filenames:
            return {
                "formatted_context": "",
                "evidence_quality": "Low",
                "top_chunks": [],
                "query_info": {},
                "injection_detected": False,
                "filenames": [],
            }

        # 1. Query Analysis & Expansion
        query_info = QueryUnderstanding.analyze(question)
        expanded_queries = QueryExpander.expand(question, query_info)
        qtype = query_info["question_type"]

        target_top_k = RAG_COMPARISON_K if qtype == "comparison" else RAG_FINAL_K
        global_candidate_pool: List[Dict[str, Any]] = []
        doc_chunks_cache: Dict[str, List[Dict[str, Any]]] = {}

        vector_store = get_vector_store()

        for filename in filenames:
            all_doc_chunks = cls.get_document_chunks(filename, user_id=user_id)
            if not all_doc_chunks:
                continue
            doc_chunks_cache[filename] = all_doc_chunks

            # Build or retrieve BM25 index for this document
            bm25_index = get_or_build_bm25_index(filename, all_doc_chunks)

            # A. Semantic Search across all expanded query variants
            semantic_candidates: Dict[int, Dict[str, Any]] = {}
            for q_variant in expanded_queries:
                try:
                    chroma_res = vector_store.similarity_search_with_relevance_scores(
                        q_variant,
                        k=min(RAG_INITIAL_K, len(all_doc_chunks)),
                        filter={"filename": filename},
                    )
                    for doc_obj, score in chroma_res:
                        meta = doc_obj.metadata or {}
                        c_idx = meta.get("chunk_index", 0)
                        norm_score = max(0.0, min(1.0, float(score)))
                        if c_idx not in semantic_candidates or norm_score > semantic_candidates[c_idx]["semantic_score"]:
                            semantic_candidates[c_idx] = {
                                "id": f"{filename}::{c_idx}",
                                "text": doc_obj.page_content,
                                "filename": filename,
                                "chunk_index": c_idx,
                                "semantic_score": norm_score,
                                "metadata": meta,
                            }
                except Exception as sem_err:
                    try:
                        raw_docs = vector_store.similarity_search(
                            q_variant,
                            k=min(RAG_INITIAL_K, len(all_doc_chunks)),
                            filter={"filename": filename},
                        )
                        for rank_idx, doc_obj in enumerate(raw_docs):
                            meta = doc_obj.metadata or {}
                            c_idx = meta.get("chunk_index", rank_idx)
                            approx_score = 1.0 / (rank_idx + 1.5)
                            if c_idx not in semantic_candidates:
                                semantic_candidates[c_idx] = {
                                    "id": f"{filename}::{c_idx}",
                                    "text": doc_obj.page_content,
                                    "filename": filename,
                                    "chunk_index": c_idx,
                                    "semantic_score": approx_score,
                                    "metadata": meta,
                                }
                    except Exception as fallback_err:
                        print(f"⚠️ Chroma search error on {filename}:", str(fallback_err))

            # B. Lexical BM25 Search across expanded queries
            lexical_candidates: Dict[int, float] = {}
            max_bm25 = 1.0
            for q_variant in expanded_queries:
                bm25_matches = bm25_index.search(q_variant, k=RAG_INITIAL_K)
                for chunk_item, score in bm25_matches:
                    c_idx = chunk_item.get("chunk_index", 0)
                    if score > max_bm25:
                        max_bm25 = score
                    if c_idx not in lexical_candidates or score > lexical_candidates[c_idx]:
                        lexical_candidates[c_idx] = score

            # Normalize BM25 scores to [0, 1]
            normalized_bm25: Dict[int, float] = {}
            for c_idx, raw_score in lexical_candidates.items():
                normalized_bm25[c_idx] = min(1.0, raw_score / max_bm25) if max_bm25 > 0 else 0.0

            # C. Hybrid Score Merging & Fusion
            all_candidate_indices = set(semantic_candidates.keys()).union(set(normalized_bm25.keys()))

            for c_idx in all_candidate_indices:
                chunk_record = all_doc_chunks[c_idx] if c_idx < len(all_doc_chunks) else None
                chunk_text = (
                    semantic_candidates.get(c_idx, {}).get("text")
                    or (chunk_record.get("text") if chunk_record else "")
                )
                if not chunk_text:
                    continue

                s_score = semantic_candidates.get(c_idx, {}).get("semantic_score", 0.0)
                l_score = normalized_bm25.get(c_idx, 0.0)

                hybrid_score = (RAG_SEMANTIC_WEIGHT * s_score) + (RAG_LEXICAL_WEIGHT * l_score)

                global_candidate_pool.append({
                    "id": f"{filename}::{c_idx}",
                    "text": chunk_text,
                    "filename": filename,
                    "chunk_index": c_idx,
                    "page_number": chunk_record.get("page_number", 1) if chunk_record else 1,
                    "extraction_method": chunk_record.get("extraction_method", "native") if chunk_record else "native",
                    "semantic_score": s_score,
                    "lexical_score": l_score,
                    "hybrid_score": hybrid_score,
                    "metadata": chunk_record.get("metadata", {}) if chunk_record else {},
                })

        if not global_candidate_pool:
            return {
                "formatted_context": "",
                "evidence_quality": "Low",
                "top_chunks": [],
                "query_info": query_info,
                "injection_detected": False,
                "filenames": filenames,
            }

        # D. GLOBAL TRUE CROSS-ENCODER RERANKING
        # Merged candidate pool from all authorized documents is reranked together
        reranked_pool = cls._rerank_candidates(question, global_candidate_pool)

        # Apply candidate pool cutoff
        pool_cutoff = target_top_k * (len(filenames) if qtype == "comparison" else 1)
        top_candidates = reranked_pool[:pool_cutoff]

        # E. Context Window Expansion (Parent-Child proximity expansion)
        expanded_candidates: List[Dict[str, Any]] = []
        for c in top_candidates:
            fname = c["filename"]
            all_chunks = doc_chunks_cache.get(fname, [])
            expanded = cls._expand_single_chunk_window(c, all_chunks)
            expanded_candidates.append(expanded)

        # F. Contextual Compression (remove noise while preserving facts)
        final_chunks = cls._contextual_compression(expanded_candidates, question)

        # G. Prompt Injection Shield & Untrusted Data Isolation
        injection_threats = PromptInjectionShield.scan_for_injection(question)
        for c in final_chunks:
            chunk_threats = PromptInjectionShield.scan_for_injection(c["text"])
            if chunk_threats:
                injection_threats.extend(chunk_threats)

        has_injection = len(injection_threats) > 0

        # Wrap chunks in strict XML containment
        formatted_context = PromptInjectionShield.wrap_isolated_context(final_chunks)

        # H. Compute Evidence Quality
        evidence_quality = cls._calculate_evidence_quality(final_chunks, query_info)

        elapsed_ms = (time.time() - t_start) * 1000
        reranker_type = final_chunks[0].get("reranker_type", "Cross-Encoder (Transformer)") if final_chunks else "none"
        print(f"⚡ [ADVANCED RAG RETRIEVAL] Query: '{question[:50]}...' | Docs: {len(filenames)} | Chunks: {len(final_chunks)} | Quality: {evidence_quality} | Reranker: {reranker_type} | Time: {elapsed_ms:.1f}ms")

        # Record structured audit event
        log_privacy_event(
            event_type="RETRIEVAL_EXECUTED",
            user_id=user_id,
            document_ids=filenames,
            privacy_risk="LOW",
            injection_detected=has_injection,
            redaction_applied=False,
            model_used="gemini",
            evidence_quality=evidence_quality,
            details={"chunk_count": len(final_chunks), "elapsed_ms": round(elapsed_ms, 2), "reranker": reranker_type},
        )

        return {
            "formatted_context": formatted_context,
            "evidence_quality": evidence_quality,
            "top_chunks": final_chunks,
            "query_info": query_info,
            "injection_detected": has_injection,
            "filenames": filenames,
        }

    @classmethod
    def _rerank_candidates(cls, query: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Rerank candidate chunks using TRUE Local Transformer Cross-Encoder.
        Batches (query, candidate_text) pairs and performs joint attention prediction.
        Gracefully falls back to embedding cosine reranking, then to hybrid score ranking.
        """
        if not candidates or not RAG_RERANKER_ENABLED:
            candidates.sort(key=lambda x: x.get("hybrid_score", 0.0), reverse=True)
            return candidates

        # 1. Try True Transformer Cross-Encoder Reranker
        try:
            ce_model = get_cross_encoder()
            if ce_model is not None:
                t_ce_start = time.time()
                pairs = [[query, c["text"]] for c in candidates]
                raw_predictions = ce_model.predict(pairs)

                for i, c in enumerate(candidates):
                    raw_score = float(raw_predictions[i])
                    norm_score = sigmoid(raw_score)
                    h_score = c.get("hybrid_score", 0.0)

                    final_score = (RAG_RERANKER_CROSS_ENCODER_WEIGHT * norm_score) + (RAG_RERANKER_HYBRID_WEIGHT * h_score)

                    c["cross_encoder_score"] = raw_score
                    c["cross_encoder_normalized"] = norm_score
                    c["rerank_score"] = final_score
                    c["reranker_type"] = "Cross-Encoder (Transformer)"

                candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
                ce_time_ms = (time.time() - t_ce_start) * 1000
                top_ce = candidates[0].get("cross_encoder_score", 0.0)
                top_norm = candidates[0].get("cross_encoder_normalized", 0.0)
                print(f"⚡ [CROSS-ENCODER RERANKER] Model: {RAG_RERANKER_MODEL} | Pairs: {len(pairs)} | Top Score: {top_ce:.4f} (Norm: {top_norm:.4f}) | Time: {ce_time_ms:.2f}ms")
                return candidates
        except Exception as ce_exc:
            print(f"⚠️ Cross-Encoder prediction failed: {ce_exc}. Falling back to cosine reranking.")

        # 2. Fallback: Local Embedding Cosine Similarity Reranking
        try:
            q_emb = embedding_model.embed_query(query)
            texts = [c["text"] for c in candidates]
            doc_embs = embedding_model.embed_documents(texts)

            for i, c in enumerate(candidates):
                d_emb = doc_embs[i]
                dot = sum(a * b for a, b in zip(q_emb, d_emb))
                norm_q = math.sqrt(sum(a * a for a in q_emb)) or 1.0
                norm_d = math.sqrt(sum(b * b for b in d_emb)) or 1.0
                cosine_sim = max(0.0, dot / (norm_q * norm_d))

                c["cosine_score"] = cosine_sim
                c["rerank_score"] = (0.7 * cosine_sim) + (0.3 * c.get("hybrid_score", 0.0))
                c["reranker_type"] = "Cosine Embedding (Fallback)"

            candidates.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
            print("ℹ️ Cosine similarity fallback reranking completed.")
            return candidates
        except Exception as cos_exc:
            print(f"⚠️ Cosine fallback failed: {cos_exc}. Falling back to hybrid scores.")

        # 3. Last Fallback: Pure Hybrid Score Ranking
        for c in candidates:
            c["rerank_score"] = c.get("hybrid_score", 0.0)
            c["reranker_type"] = "Hybrid Score (Fallback)"
        candidates.sort(key=lambda x: x.get("hybrid_score", 0.0), reverse=True)
        return candidates

    @classmethod
    def _expand_single_chunk_window(cls, chunk: Dict[str, Any], all_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Expand single chunk with adjacent context (Parent-Child windowing) when beneficial."""
        if not all_chunks:
            return chunk

        chunk_map = {c["chunk_index"]: c for c in all_chunks}
        c_idx = chunk["chunk_index"]
        combined_text = chunk["text"]

        if chunk.get("rerank_score", 0.0) > 0.45:
            # Preceding chunk
            if (c_idx - 1) in chunk_map:
                prev_text = chunk_map[c_idx - 1]["text"].strip()
                if len(prev_text) < 400:
                    combined_text = prev_text + "\n" + combined_text
            # Succeeding chunk
            if (c_idx + 1) in chunk_map:
                next_text = chunk_map[c_idx + 1]["text"].strip()
                if len(next_text) < 400:
                    combined_text = combined_text + "\n" + next_text

        return {
            **chunk,
            "text": combined_text,
        }

    @classmethod
    def _contextual_compression(cls, chunks: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """Filter out duplicate boilerplate sentences while preserving numbers, facts, and entities."""
        if not chunks or not RAG_COMPRESSION_ENABLED:
            return chunks

        compressed = []
        q_tokens = set(re.findall(r"[A-Za-z0-9]+", query.lower()))

        for c in chunks:
            raw_text = c.get("text", "").strip()
            lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

            meaningful_lines = []
            for line in lines:
                has_digits = bool(re.search(r"\d", line))
                is_bullet = bool(re.match(r"^(?:[-*•#]|\d+[.)])", line))
                has_keywords = bool(set(re.findall(r"[A-Za-z0-9]+", line.lower())).intersection(q_tokens))

                if has_digits or is_bullet or has_keywords or len(line) > 60:
                    meaningful_lines.append(line)

            final_text = "\n".join(meaningful_lines) if meaningful_lines else raw_text
            compressed.append({
                **c,
                "text": final_text,
            })

        return compressed

    @staticmethod
    def _calculate_evidence_quality(chunks: List[Dict[str, Any]], query_info: Dict[str, Any]) -> str:
        """Calculate evidence quality indicator: High, Medium, or Low."""
        if not chunks:
            return "Low"

        top_score = max((c.get("rerank_score", c.get("hybrid_score", 0.0)) for c in chunks), default=0.0)
        total_chunks = len(chunks)

        if top_score >= 0.55 and total_chunks >= 2:
            return "High"
        elif top_score >= 0.35 or total_chunks >= 1:
            return "Medium"
        return "Low"
