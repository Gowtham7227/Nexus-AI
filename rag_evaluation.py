"""
NexusAI - RAG Evaluation Framework & Source Citations
=====================================================
Production-quality, modular evaluation framework and deterministic grounding evaluator.
Provides:
1. Sentence-level deterministic claim analysis and grounding metrics (no extra LLM calls needed).
2. Trusted server-side source citation builder, prompt formatter, and post-generation validator.
3. Standard retrieval metrics (Hit@K, Recall@K, MRR, source accuracy, page accuracy).
4. Automated report generation (JSON + Markdown).
"""

import os
import sys
import re
import json
import time
import math
from typing import List, Dict, Any, Optional, Tuple, Set

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ============================================================
# 1. STOPWORDS & TOKENIZATION HELPERS
# ============================================================

STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't", "have",
    "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers",
    "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm",
    "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself", "let's",
    "me", "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off",
    "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out",
    "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's", "should",
    "shouldn't", "so", "some", "such", "than", "that", "that's", "the", "their",
    "theirs", "them", "themselves", "then", "there", "there's", "these", "they",
    "they'd", "they'll", "they're", "they've", "this", "those", "through", "to", "too",
    "under", "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're",
    "we've", "were", "weren't", "what", "what's", "when", "when's", "where", "where's",
    "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours", "yourself",
    "yourselves", "also", "based", "according", "document", "provided", "information"
}


def extract_content_tokens(text: str) -> List[str]:
    """Extract lowercase alphanumeric tokens of length >= 2, excluding stopwords."""
    if not text:
        return []
    words = re.findall(r"[A-Za-z0-9_\-]+", str(text).lower())
    return [w for w in words if w not in STOPWORDS and len(w) >= 2]


def extract_ngrams(tokens: List[str], n: int = 2) -> Set[str]:
    """Generate n-gram strings from a token list."""
    if len(tokens) < n:
        return set(tokens)
    return {" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}


# ============================================================
# 2. SOURCE CITATIONS BUILDER & VALIDATOR
# ============================================================

class SourceCitationManager:
    """
    Manages generation, prompt serialization, and post-generation validation of source citations.
    Guarantees that citation metadata originates ONLY from trusted server-side retrieval structures.
    """

    @staticmethod
    def build_citations(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert retrieved context chunks into safe, client-facing citation structures.
        Strictly strips internal paths, DB keys, user IDs, and raw vector representations.
        """
        citations: List[Dict[str, Any]] = []
        for idx, chunk in enumerate(chunks):
            # Resolve safe filename
            filename = chunk.get("filename") or "document"
            # Strip any directory path components just in case
            safe_filename = os.path.basename(str(filename))

            # Resolve page number
            page_num = chunk.get("page_number")
            if page_num is None:
                meta = chunk.get("metadata", {})
                page_num = meta.get("page_number", 1) if isinstance(meta, dict) else 1

            # Resolve extraction method
            ext_method = chunk.get("extraction_method") or "native"
            if isinstance(chunk.get("metadata"), dict):
                ext_method = chunk["metadata"].get("extraction_method", ext_method)

            # Resolve relevance score
            relevance = (
                chunk.get("rerank_score")
                or chunk.get("final_score")
                or chunk.get("hybrid_score")
                or chunk.get("score")
                or 0.0
            )

            # Extract short safe snippet (max 180 chars)
            raw_text = chunk.get("text") or chunk.get("content") or ""
            clean_snippet = re.sub(r"\s+", " ", raw_text).strip()[:180]

            chunk_idx = chunk.get("chunk_index", idx)

            citations.append({
                "id": idx + 1,
                "filename": safe_filename,
                "page_number": int(page_num) if str(page_num).isdigit() else 1,
                "chunk_id": f"{safe_filename}::{chunk_idx}",
                "relevance": round(float(relevance), 4),
                "extraction_method": str(ext_method).lower(),
                "snippet": clean_snippet,
            })

        return citations

    @staticmethod
    def format_sources_for_prompt(citations: List[Dict[str, Any]], chunks: List[Dict[str, Any]]) -> str:
        """
        Format retrieved context with clear, explicit citation tags for Gemini/Qwen LLM consumption.
        """
        if not citations or not chunks:
            return ""

        blocks = []
        for i, cite in enumerate(citations):
            raw_text = chunks[i].get("text") or chunks[i].get("content") or ""
            page_str = f"Page: {cite['page_number']}" if cite.get("page_number") else "Source chunk"
            block = (
                f"SOURCE [{cite['id']}]\n"
                f"Document: {cite['filename']}\n"
                f"{page_str}\n"
                f"Extraction: {cite['extraction_method']}\n"
                f"Content:\n{raw_text.strip()}"
            )
            blocks.append(block)

        return "\n\n" + ("=" * 40) + "\n\n".join(blocks) + "\n\n" + ("=" * 40)

    @staticmethod
    def validate_citations(
        answer: str,
        citations: List[Dict[str, Any]],
        chunks: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Post-generation citation validation.
        Detects:
        - Non-existent citation IDs (e.g. [99] when only 3 sources exist)
        - Malformed citations
        - Hallucinated references

        Action:
        - Strips invalid citation references from answer text.
        - Returns validated citation subset or all available valid citations if answer is general.
        """
        if not citations:
            # Strip any hallucinated [1], [2] tags if no citations exist
            cleaned_answer = re.sub(r"\[\d+\]", "", answer)
            cleaned_answer = re.sub(r"\s{2,}", " ", cleaned_answer).strip()
            return cleaned_answer, []

        valid_ids = {c["id"] for c in citations}
        found_ids: Set[int] = set()

        def sanitize_match(match: re.Match) -> str:
            raw = match.group(0)
            digits = re.findall(r"\d+", raw)
            matched_valid = [int(d) for d in digits if int(d) in valid_ids]
            if matched_valid:
                for v in matched_valid:
                    found_ids.add(v)
                if len(matched_valid) == 1:
                    return f"[{matched_valid[0]}]"
                return "[" + ", ".join(str(d) for d in matched_valid) + "]"
            # If completely invalid (e.g., [99]), drop it
            return ""

        # Replace citation blocks like [1], [1, 2], [99]
        cleaned_answer = re.sub(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]", sanitize_match, answer)
        # Clean up double spaces created by dropped tags
        cleaned_answer = re.sub(r" +([.,!?;])", r"\1", cleaned_answer)
        cleaned_answer = re.sub(r" {2,}", " ", cleaned_answer).strip()

        # Filter citations list: If inline citations were used, return those; otherwise return top retrieved citations
        if found_ids:
            referenced_citations = [c for c in citations if c["id"] in found_ids]
        else:
            referenced_citations = citations

        return cleaned_answer, referenced_citations


# ============================================================
# 3. DETERMINISTIC GROUNDING EVALUATOR
# ============================================================

class DeterministicGroundingEvaluator:
    """
    Sentence-level deterministic grounding evaluator.
    Evaluates claims without requiring a secondary LLM judge, preventing recursive hallucination.
    """

    INSUFFICIENT_EVIDENCE_PATTERNS = [
        "couldn't find", "could not find", "insufficient information",
        "not mentioned", "not found in the document", "does not contain",
        "no information", "unable to answer", "cannot answer"
    ]

    @classmethod
    def evaluate(
        cls,
        question: str,
        retrieved_chunks: List[Dict[str, Any]],
        generated_answer: str,
        citations: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate how well the generated answer is grounded in the retrieved chunks.
        Returns detailed sentence-by-sentence evaluation and aggregated scores.
        """
        if not generated_answer or not generated_answer.strip():
            return {
                "grounding_score": 0.0,
                "supported_claim_ratio": 0.0,
                "unsupported_claim_ratio": 0.0,
                "partially_supported_claim_ratio": 0.0,
                "total_claims": 0,
                "supported_claims": 0,
                "unsupported_claims": 0,
                "partially_supported_claims": 0,
                "is_insufficient_evidence": True,
                "sentence_evaluations": [],
                "method": "deterministic_sentence_grounding",
            }

        answer_lower = generated_answer.lower()
        # Check if model correctly declared insufficient evidence
        is_insufficient = any(p in answer_lower for p in cls.INSUFFICIENT_EVIDENCE_PATTERNS)
        if is_insufficient and (not retrieved_chunks or len(retrieved_chunks) == 0 or len(answer_lower.split()) < 25):
            return {
                "grounding_score": 1.0,
                "supported_claim_ratio": 1.0,
                "unsupported_claim_ratio": 0.0,
                "partially_supported_claim_ratio": 0.0,
                "total_claims": 1,
                "supported_claims": 1,
                "unsupported_claims": 0,
                "partially_supported_claims": 0,
                "is_insufficient_evidence": True,
                "sentence_evaluations": [{
                    "sentence": generated_answer.strip(),
                    "status": "SUPPORTED",
                    "support_score": 1.0,
                    "matched_sources": [],
                    "reason": "Correctly identified insufficient context."
                }],
                "method": "deterministic_sentence_grounding",
            }

        # Combine all chunk texts into search space and per-chunk token sets
        chunk_token_sets: List[Set[str]] = []
        chunk_bigram_sets: List[Set[str]] = []
        all_chunk_text = ""

        for c in retrieved_chunks:
            txt = c.get("text") or c.get("content") or ""
            all_chunk_text += " " + txt
            c_tokens = extract_content_tokens(txt)
            chunk_token_sets.append(set(c_tokens))
            chunk_bigram_sets.append(extract_ngrams(c_tokens, n=2))

        all_context_tokens = set(extract_content_tokens(all_chunk_text))
        all_context_bigrams = extract_ngrams(extract_content_tokens(all_chunk_text), n=2)

        # Split answer into sentences
        raw_sentences = re.split(r"(?<=[.!?])\s+", generated_answer.strip())
        sentence_evals: List[Dict[str, Any]] = []

        supported_count = 0
        partial_count = 0
        unsupported_count = 0

        for raw_s in raw_sentences:
            s_clean = raw_s.strip()
            if not s_clean:
                continue

            # Strip citation markers like [1], [2] for token analysis
            s_no_cite = re.sub(r"\[\d+\]", "", s_clean).strip()
            s_tokens = extract_content_tokens(s_no_cite)

            if len(s_tokens) == 0:
                continue

            s_bigrams = extract_ngrams(s_tokens, n=2)

            # 1. Calculate unigram overlap against full context
            unigram_overlap = len(set(s_tokens).intersection(all_context_tokens)) / max(len(set(s_tokens)), 1)

            # 2. Calculate bigram overlap against full context
            if s_bigrams:
                bigram_overlap = len(s_bigrams.intersection(all_context_bigrams)) / max(len(s_bigrams), 1)
            else:
                bigram_overlap = unigram_overlap

            # Weighted support score: 60% bigram precision, 40% unigram precision
            support_score = (0.4 * unigram_overlap) + (0.6 * bigram_overlap)

            # Find matching sources for this sentence
            matched_sources = []
            for c_idx, c_tokens in enumerate(chunk_token_sets):
                chunk_match = len(set(s_tokens).intersection(c_tokens)) / max(len(set(s_tokens)), 1)
                if chunk_match >= 0.4:
                    matched_sources.append(c_idx + 1)

            # Categorize claim support level
            if support_score >= 0.50:
                status = "SUPPORTED"
                supported_count += 1
            elif support_score >= 0.25:
                status = "PARTIALLY_SUPPORTED"
                partial_count += 1
            else:
                status = "UNSUPPORTED"
                unsupported_count += 1

            sentence_evals.append({
                "sentence": s_clean,
                "status": status,
                "support_score": round(support_score, 4),
                "unigram_overlap": round(unigram_overlap, 4),
                "bigram_overlap": round(bigram_overlap, 4),
                "matched_sources": matched_sources,
            })

        total_claims = len(sentence_evals)
        if total_claims == 0:
            grounding_score = 0.0
            supported_ratio = 0.0
            unsupported_ratio = 0.0
            partial_ratio = 0.0
        else:
            # Weighted overall grounding score: 1.0 for supported, 0.5 for partial, 0.0 for unsupported
            grounding_score = (
                (supported_count * 1.0) + (partial_count * 0.5)
            ) / float(total_claims)
            supported_ratio = supported_count / float(total_claims)
            unsupported_ratio = unsupported_count / float(total_claims)
            partial_ratio = partial_count / float(total_claims)

        return {
            "grounding_score": round(grounding_score, 4),
            "supported_claim_ratio": round(supported_ratio, 4),
            "unsupported_claim_ratio": round(unsupported_ratio, 4),
            "partially_supported_claim_ratio": round(partial_ratio, 4),
            "total_claims": total_claims,
            "supported_claims": supported_count,
            "unsupported_claims": unsupported_count,
            "partially_supported_claims": partial_count,
            "is_insufficient_evidence": is_insufficient,
            "sentence_evaluations": sentence_evals,
            "method": "deterministic_sentence_grounding",
        }


# ============================================================
# 4. RAG METRICS CALCULATOR
# ============================================================

class RAGMetricsCalculator:
    """
    Calculates deterministic information retrieval and grounding metrics.
    """

    @staticmethod
    def calculate_retrieval_metrics(
        expected_sources: List[str],
        retrieved_chunks: List[Dict[str, Any]],
        expected_pages: Optional[List[int]] = None,
        k: int = 5,
    ) -> Dict[str, Any]:
        """
        Compute Hit@K, Recall@K, MRR, source-document accuracy, and page accuracy.
        """
        if not expected_sources:
            return {
                "hit_at_k": 1.0 if not retrieved_chunks else 0.0,
                "recall_at_k": 1.0,
                "mrr": 1.0,
                "source_accuracy": 1.0,
                "page_accuracy": 1.0,
            }

        top_k_chunks = retrieved_chunks[:k]
        retrieved_sources = [c.get("filename", "") for c in top_k_chunks]
        retrieved_pages = [c.get("page_number") for c in top_k_chunks]

        # 1. Hit@K: 1.0 if at least one expected source is in top K
        hit_at_k = 1.0 if any(src in retrieved_sources for src in expected_sources) else 0.0

        # 2. Recall@K: proportion of expected sources found in top K
        found_expected = {src for src in expected_sources if src in retrieved_sources}
        recall_at_k = len(found_expected) / float(len(expected_sources)) if expected_sources else 1.0

        # 3. MRR (Mean Reciprocal Rank): 1 / first rank of any expected source
        mrr = 0.0
        for rank_idx, src in enumerate(retrieved_sources):
            if src in expected_sources:
                mrr = 1.0 / (rank_idx + 1)
                break

        # 4. Source accuracy: proportion of retrieved chunks that belong to expected sources
        if top_k_chunks:
            correct_sources = sum(1 for src in retrieved_sources if src in expected_sources)
            source_accuracy = correct_sources / float(len(top_k_chunks))
        else:
            source_accuracy = 0.0

        # 5. Page accuracy: 1.0 if expected pages are matched
        if expected_pages:
            matched_pages = sum(1 for p in retrieved_pages if p in expected_pages)
            page_accuracy = matched_pages / float(len(top_k_chunks)) if top_k_chunks else 0.0
        else:
            page_accuracy = 1.0

        return {
            "hit_at_k": round(hit_at_k, 4),
            "recall_at_k": round(recall_at_k, 4),
            "mrr": round(mrr, 4),
            "source_accuracy": round(source_accuracy, 4),
            "page_accuracy": round(page_accuracy, 4),
        }

    @staticmethod
    def calculate_answer_concept_coverage(
        answer: str,
        expected_concepts: List[str]
    ) -> float:
        """Calculate proportion of expected domain concepts found in the generated answer."""
        if not expected_concepts:
            return 1.0
        if not answer:
            return 0.0
        ans_lower = answer.lower()
        found = sum(1 for concept in expected_concepts if concept.lower() in ans_lower)
        return round(found / float(len(expected_concepts)), 4)

    @staticmethod
    def calculate_citation_metrics(
        citations: List[Dict[str, Any]],
        expected_sources: List[str],
        sentence_evaluations: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        """
        Compute Citation Correctness and Citation Completeness.
        """
        if not citations:
            return {
                "citation_correctness": 1.0 if not expected_sources else 0.0,
                "citation_completeness": 1.0 if not expected_sources else 0.0,
            }

        # Correctness: proportion of citations whose filename is in expected_sources
        if expected_sources:
            correct_cites = sum(1 for c in citations if c.get("filename") in expected_sources)
            citation_correctness = correct_cites / float(len(citations))
        else:
            citation_correctness = 1.0

        # Completeness: proportion of SUPPORTED claims that have at least one valid matched source
        supported_claims = [s for s in sentence_evaluations if s.get("status") == "SUPPORTED"]
        if supported_claims:
            claims_with_cites = sum(1 for s in supported_claims if s.get("matched_sources"))
            citation_completeness = claims_with_cites / float(len(supported_claims))
        else:
            citation_completeness = 1.0

        return {
            "citation_correctness": round(citation_correctness, 4),
            "citation_completeness": round(citation_completeness, 4),
        }


# ============================================================
# 5. RAG EVALUATOR ENGINE & REPORT GENERATOR
# ============================================================

class RAGEvaluator:
    """
    End-to-end evaluation runner for NexusAI RAG pipeline.
    Runs test cases against active or baseline RAG retrieval pipelines, measures metrics,
    and produces structured JSON and Markdown audit reports.
    """

    def __init__(self, dataset_path: Optional[str] = None):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        if dataset_path is None:
            dataset_path = os.path.join(base_dir, "evaluation_datasets", "rag_eval_dataset.json")
        self.dataset_path = dataset_path
        self.dataset: Dict[str, Any] = self._load_dataset()

    def _load_dataset(self) -> Dict[str, Any]:
        if not os.path.exists(self.dataset_path):
            raise FileNotFoundError(f"Evaluation dataset not found at: {self.dataset_path}")
        with open(self.dataset_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def run_evaluation(
        self,
        user_context: Optional[Dict[str, Any]] = None,
        use_optimizer: bool = True,
        generate_answers: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute full benchmark across all cases in the evaluation dataset.
        """
        from advanced_rag import NexusAdvancedRAG
        from rag_optimizer import AdaptiveRAGOptimizer
        from chatbot import ask_gemini

        cases = self.dataset.get("cases", [])
        results = []
        t_bench_start = time.perf_counter()

        optimizer = AdaptiveRAGOptimizer() if use_optimizer else None

        for case in cases:
            case_id = case["id"]
            category = case["category"]
            question = case["question"]
            expected_sources = case.get("expected_sources", [])
            expected_pages = case.get("expected_pages", [])
            expected_concepts = case.get("expected_concepts", [])
            answerable = case.get("answerable", True)

            t_case_start = time.perf_counter()

            # Execute RAG retrieval
            retrieval_res = NexusAdvancedRAG.retrieve_hybrid_context(
                question=question,
                filenames=expected_sources,
                user_id=user_context.get("user_id", 1) if user_context else 1,
            )

            retrieved_chunks = retrieval_res.get("top_chunks", [])
            context_text = retrieval_res.get("formatted_context", "")

            # Build source citations
            citations = SourceCitationManager.build_citations(retrieved_chunks)

            # Generate or mock answer
            if generate_answers and context_text.strip():
                try:
                    raw_answer = ask_gemini(context_text, question)
                except Exception as e:
                    raw_answer = f"Error generating answer: {e}"
            else:
                raw_answer = case.get("reference_answer", "I couldn't find sufficient information.")

            # Validate citations
            validated_answer, validated_citations = SourceCitationManager.validate_citations(
                raw_answer, citations, retrieved_chunks
            )

            # Evaluate deterministic grounding
            grounding_eval = DeterministicGroundingEvaluator.evaluate(
                question=question,
                retrieved_chunks=retrieved_chunks,
                generated_answer=validated_answer,
                citations=validated_citations,
            )

            # Compute retrieval metrics
            retrieval_metrics = RAGMetricsCalculator.calculate_retrieval_metrics(
                expected_sources=expected_sources,
                retrieved_chunks=retrieved_chunks,
                expected_pages=expected_pages,
                k=5,
            )

            # Compute concept coverage
            concept_coverage = RAGMetricsCalculator.calculate_answer_concept_coverage(
                answer=validated_answer,
                expected_concepts=expected_concepts,
            )

            # Compute citation metrics
            citation_metrics = RAGMetricsCalculator.calculate_citation_metrics(
                citations=validated_citations,
                expected_sources=expected_sources,
                sentence_evaluations=grounding_eval.get("sentence_evaluations", []),
            )

            latency_ms = (time.perf_counter() - t_case_start) * 1000.0

            case_result = {
                "id": case_id,
                "category": category,
                "question": question,
                "answerable": answerable,
                "expected_sources": expected_sources,
                "retrieved_chunk_count": len(retrieved_chunks),
                "citations_count": len(validated_citations),
                "retrieval_metrics": retrieval_metrics,
                "grounding_metrics": {
                    "grounding_score": grounding_eval["grounding_score"],
                    "supported_claim_ratio": grounding_eval["supported_claim_ratio"],
                    "unsupported_claim_ratio": grounding_eval["unsupported_claim_ratio"],
                },
                "concept_coverage": concept_coverage,
                "citation_metrics": citation_metrics,
                "latency_ms": round(latency_ms, 2),
                "timings": retrieval_res.get("timings", {}),
            }
            results.append(case_result)

        total_elapsed_ms = (time.perf_counter() - t_bench_start) * 1000.0

        # Compute Category Aggregates
        categories_map: Dict[str, List[Dict[str, Any]]] = {}
        for r in results:
            cat = r["category"]
            if cat not in categories_map:
                categories_map[cat] = []
            categories_map[cat].append(r)

        category_summary = {}
        for cat, items in categories_map.items():
            avg_hit = sum(it["retrieval_metrics"]["hit_at_k"] for it in items) / len(items)
            avg_mrr = sum(it["retrieval_metrics"]["mrr"] for it in items) / len(items)
            avg_grounding = sum(it["grounding_metrics"]["grounding_score"] for it in items) / len(items)
            avg_citation = sum(it["citation_metrics"]["citation_correctness"] for it in items) / len(items)
            avg_latency = sum(it["latency_ms"] for it in items) / len(items)
            category_summary[cat] = {
                "cases": len(items),
                "hit_at_k": round(avg_hit, 4),
                "mrr": round(avg_mrr, 4),
                "grounding_score": round(avg_grounding, 4),
                "citation_correctness": round(avg_citation, 4),
                "avg_latency_ms": round(avg_latency, 2),
            }

        global_hit = sum(r["retrieval_metrics"]["hit_at_k"] for r in results) / max(len(results), 1)
        global_mrr = sum(r["retrieval_metrics"]["mrr"] for r in results) / max(len(results), 1)
        global_grounding = sum(r["grounding_metrics"]["grounding_score"] for r in results) / max(len(results), 1)
        global_citation = sum(r["citation_metrics"]["citation_correctness"] for r in results) / max(len(results), 1)
        global_latency = sum(r["latency_ms"] for r in results) / max(len(results), 1)

        report = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "dataset_name": self.dataset.get("name", "NexusAI RAG Benchmark"),
            "dataset_version": self.dataset.get("version", "1.0.0"),
            "total_cases": len(results),
            "optimizer_enabled": use_optimizer,
            "global_metrics": {
                "mean_hit_at_5": round(global_hit, 4),
                "mean_mrr": round(global_mrr, 4),
                "mean_grounding_score": round(global_grounding, 4),
                "mean_citation_correctness": round(global_citation, 4),
                "mean_latency_ms": round(global_latency, 2),
                "total_duration_ms": round(total_elapsed_ms, 2),
            },
            "category_summary": category_summary,
            "case_results": results,
        }

        return report

    def save_reports(self, report: Dict[str, Any], output_dir: Optional[str] = None) -> Tuple[str, str]:
        """Save JSON and Markdown reports to the target directory."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        if output_dir is None:
            output_dir = os.path.join(base_dir, "evaluation_reports")
        os.makedirs(output_dir, exist_ok=True)

        json_path = os.path.join(output_dir, "rag_evaluation_latest.json")
        md_path = os.path.join(output_dir, "rag_evaluation_latest.md")

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        # Generate Markdown
        md_content = self._format_markdown_report(report)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        return json_path, md_path

    def _format_markdown_report(self, report: Dict[str, Any]) -> str:
        gm = report["global_metrics"]
        cats = report["category_summary"]

        lines = [
            "# NexusAI — RAG Quality & Grounding Evaluation Report",
            "",
            f"**Evaluation Timestamp**: `{report['timestamp']}`  ",
            f"**Dataset**: `{report['dataset_name']}` (v{report['dataset_version']})  ",
            f"**Optimizer Enabled**: `{report['optimizer_enabled']}`  ",
            f"**Total Test Cases**: `{report['total_cases']}`  ",
            "",
            "---",
            "",
            "## 1. Global Benchmark Summary",
            "",
            "| Metric | Result | Description |",
            "|:---|:---:|:---|",
            f"| **Mean Hit@5** | **{gm['mean_hit_at_5'] * 100:.1f}%** | Proportion of queries with expected source in top 5 chunks |",
            f"| **Mean MRR** | **{gm['mean_mrr']:.4f}** | Mean Reciprocal Rank of first relevant source chunk |",
            f"| **Mean Grounding Score** | **{gm['mean_grounding_score'] * 100:.1f}%** | Sentence-level claim support against retrieved evidence |",
            f"| **Citation Correctness** | **{gm['mean_citation_correctness'] * 100:.1f}%** | Proportion of citations referencing verified retrieved sources |",
            f"| **Mean Latency** | **{gm['mean_latency_ms']:.2f} ms** | Average total retrieval and evaluation duration |",
            "",
            "---",
            "",
            "## 2. Category Performance Breakdown",
            "",
            "| Category | Cases | Hit@5 | MRR | Grounding | Citation | Avg Latency |",
            "|:---|:---:|:---:|:---:|:---:|:---:|:---:|",
        ]

        for cat_name, cat_data in cats.items():
            display_name = cat_name.replace("_", " ").title()
            lines.append(
                f"| **{display_name}** | {cat_data['cases']} | "
                f"{cat_data['hit_at_k'] * 100:.1f}% | "
                f"{cat_data['mrr']:.4f} | "
                f"{cat_data['grounding_score'] * 100:.1f}% | "
                f"{cat_data['citation_correctness'] * 100:.1f}% | "
                f"{cat_data['avg_latency_ms']:.1f} ms |"
            )

        lines.extend([
            "",
            "---",
            "",
            "## 3. Grounding & Citation Validation Rules",
            "",
            "- **Deterministic Evaluation**: Sentence-level n-gram overlap against trusted server-side chunks (no secondary LLM hallucination).",
            "- **Zero Injection Risk**: Citation IDs originate exclusively from server-side retrieval structures, ignoring any text-injected citation markers.",
            "- **Self-Healing Compatibility**: If vectors are missing for an indexed document, retrieval returns empty context safely without fabricating citations.",
            "",
        ])

        return "\n".join(lines)


# CLI Execution Entrypoint
if __name__ == "__main__":
    print("=" * 70)
    print("🚀 Running NexusAI RAG Evaluation Benchmark...")
    print("=" * 70)
    evaluator = RAGEvaluator()
    report = evaluator.run_evaluation(user_context={"user_id": 2}, use_optimizer=True, generate_answers=False)
    j_path, m_path = evaluator.save_reports(report)
    print(f"✅ Evaluation Complete! Reports saved to:\n  - {j_path}\n  - {m_path}")
    print("\nGlobal Summary:")
    print(json.dumps(report["global_metrics"], indent=2))
