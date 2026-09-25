"""
NexusAI v1.4 - Bounded Multi-Hop & Iterative Reasoning Engine
=============================================================
Orchestrates bounded multi-hop retrieval for complex relational,
comparative, and multi-document queries with early stopping,
evidence sufficiency verification, and loop prevention.
"""

import re
import time
from typing import List, Dict, Any, Optional, Tuple
from advanced_rag import NexusAdvancedRAG
from rag_optimizer import AdaptiveRAGOptimizer
from services.verification_service import VerificationService
from services.table_extractor import TableAwareExtractor


MAX_HOPS = 3


class MultiHopReasoningService:
    """
    Coordinates bounded iterative retrieval, sub-query decomposition,
    and evidence synthesis.
    """

    # Multi-hop query pattern triggers
    _RE_MULTIHOP_TRIGGERS = re.compile(
        r"\b(?:who\s+founded\s+the\s+company\s+that|what\s+is\s+the\s+(?:revenue|budget|product|metric)\s+of\s+the|which\s+(?:company|subsidiary|division)\s+(?:has|owns|reported)|compare\s+.+\s+and\s+(?:explain|evaluate|contrast)|relationship\s+between|how\s+does\s+.+\s+impact\s+.+\s+and\s+affect|differences?\s+between\s+.+\s+and\s+.+\s+regarding|both\s+documents|across\s+all\s+documents)\b",
        re.IGNORECASE
    )

    @classmethod
    def should_use_multihop(
        cls,
        question: str,
        filenames: Optional[List[str]] = None,
        query_type: Optional[str] = None,
    ) -> bool:
        """
        Deterministically decide if query requires multi-hop iterative retrieval.
        Simple factual, direct single-doc lookups return False (staying single_pass).
        """
        if not question or not filenames:
            return False

        doc_count = len(filenames)
        q_lower = question.strip().lower()

        # If explicit comparison or complex analytical across multiple docs
        if doc_count > 1 and query_type in ("comparison", "complex_analytical", "multi_document"):
            return True

        # Regex multi-hop relational bridging trigger
        if cls._RE_MULTIHOP_TRIGGERS.search(q_lower):
            return True

        # Multi-clause relational query across multiple documents
        if doc_count > 1 and any(w in q_lower for w in (" while ", " whereas ", " compare ", " versus ", " vs ")):
            return True

        return False

    @classmethod
    def decompose_query(
        cls,
        question: str,
        filenames: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Decompose a complex question into 2 or 3 distinct sub-queries.
        Guarantees <= 3 sub-queries, strictly deduplicated.
        """
        q = question.strip()
        q_lower = q.lower()
        subqueries = []

        # 1. Comparison query: split along comparison operators
        compare_split = re.split(r"\b(?:compare|versus| vs | and | while | whereas | compared to )\b", q, flags=re.IGNORECASE)
        if len(compare_split) >= 2:
            clean_splits = [s.strip() for s in compare_split if len(s.strip().split()) >= 2]
            if len(clean_splits) >= 2:
                for s in clean_splits[:2]:
                    subqueries.append(f"{s}")
                # Optional synthesis query
                subqueries.append(f"Summary and comparison of {clean_splits[0]} and {clean_splits[1]}")

        # 2. Relational bridging ("X of Y that Z")
        if not subqueries and (" that " in q_lower or " which " in q_lower):
            parts = re.split(r"\b(?:that|which)\b", q, flags=re.IGNORECASE)
            if len(parts) >= 2:
                subqueries.append(parts[1].strip())
                subqueries.append(parts[0].strip())

        # 3. Default fallback decomposition: entity-specific subqueries
        if not subqueries:
            subqueries.append(q)
            # If multiple filenames, query individual documents
            if filenames and len(filenames) > 1:
                for fn in filenames[:2]:
                    subqueries.append(f"{q} in {fn}")

        # Deduplicate while preserving order and limit to MAX_HOPS
        seen = set()
        final_subqueries = []
        for sq in subqueries:
            sq_norm = sq.strip().lower()
            if sq_norm and sq_norm not in seen:
                seen.add(sq_norm)
                final_subqueries.append(sq.strip())
            if len(final_subqueries) >= MAX_HOPS:
                break

        return final_subqueries or [q]

    @classmethod
    def execute_multi_hop_pipeline(
        cls,
        question: str,
        filenames: List[str],
        user_id: int,
    ) -> Dict[str, Any]:
        """
        Execute bounded multi-hop iterative retrieval across authorized documents.
        Returns:
          {
            "reasoning_mode": "multi_hop" | "single_pass",
            "hop_count": int,
            "subqueries": List[str],
            "top_chunks": List[Dict],
            "formatted_context": str,
            "evidence_sufficiency": "sufficient" | "partial" | "insufficient",
            "conflict_detected": bool,
            "conflicts": List[Dict],
            "table_evidence": bool,
            "citations": List[Dict],
            "timings": Dict[str, float],
          }
        """
        t_start = time.perf_counter()
        query_type, complexity = AdaptiveRAGOptimizer.classify_query(question, filenames)
        use_multihop = cls.should_use_multihop(question, filenames, query_type)
        is_table_query = TableAwareExtractor.is_tabular_query(question)

        # Fast path: Single-pass retrieval
        if not use_multihop:
            retrieval_res = NexusAdvancedRAG.retrieve_hybrid_context(
                question,
                filenames,
                user_id=user_id,
            )
            chunks = retrieval_res.get("top_chunks", [])
            sufficiency = VerificationService.verify_evidence_sufficiency(question, chunks)
            conflict_info = VerificationService.detect_cross_document_conflicts(chunks)

            context = retrieval_res["formatted_context"]
            if conflict_info["conflict_detected"]:
                conflict_xml = VerificationService.format_conflict_grounding_annotation(conflict_info["conflicts"])
                context = f"{conflict_xml}\n\n{context}"

            elapsed_ms = (time.perf_counter() - t_start) * 1000.0
            return {
                "reasoning_mode": "single_pass",
                "hop_count": 1,
                "subqueries": [question],
                "top_chunks": chunks,
                "formatted_context": context,
                "evidence_quality": retrieval_res.get("evidence_quality", "Medium"),
                "evidence_sufficiency": sufficiency["status"],
                "sufficiency_details": sufficiency,
                "conflict_detected": conflict_info["conflict_detected"],
                "conflicts": conflict_info["conflicts"],
                "table_evidence": is_table_query,
                "citations": retrieval_res.get("citations", []),
                "timings": {
                    "reasoning_ms": round(elapsed_ms, 2),
                    "retrieval_ms": retrieval_res.get("timings", {}).get("total_retrieval_ms", 0.0),
                },
            }

        # Multi-Hop Iterative Path
        subqueries = cls.decompose_query(question, filenames)
        accumulated_chunks: List[Dict[str, Any]] = []
        seen_chunk_keys = set()
        executed_hops = 0
        all_citations: List[Dict[str, Any]] = []

        print("=" * 70)
        print(f"🔄 [MULTI-HOP REASONING START] Query='{question[:50]}...', Subqueries={len(subqueries)}, Docs={filenames}")

        for hop_idx, sub_q in enumerate(subqueries, start=1):
            if executed_hops >= MAX_HOPS:
                break

            executed_hops += 1
            print(f"  -> Hop {executed_hops}/{MAX_HOPS}: Executing sub-query '{sub_q[:60]}...'")

            # Execute authorized retrieval for this sub-query
            try:
                hop_res = NexusAdvancedRAG.retrieve_hybrid_context(
                    sub_q,
                    filenames,
                    user_id=user_id,
                )
                hop_chunks = hop_res.get("top_chunks", [])
                hop_citations = hop_res.get("citations", [])

                for c in hop_chunks:
                    c_key = (
                        c.get("metadata", {}).get("filename") or c.get("source"),
                        c.get("metadata", {}).get("chunk_index", 0),
                        c.get("metadata", {}).get("page_number", 1),
                    )
                    if c_key not in seen_chunk_keys:
                        seen_chunk_keys.add(c_key)
                        c["hop_discovered"] = executed_hops
                        accumulated_chunks.append(c)

                for cit in hop_citations:
                    if cit not in all_citations:
                        all_citations.append(cit)

            except Exception as hop_err:
                print(f"⚠️ [MULTI-HOP ERROR] Hop {executed_hops} failed: {hop_err}")
                continue

            # Check early stopping: if evidence sufficiency is reached
            sufficiency_check = VerificationService.verify_evidence_sufficiency(question, accumulated_chunks)
            if sufficiency_check["status"] == "sufficient" and executed_hops >= 2:
                print(f"  ✅ Early stopping at Hop {executed_hops}: Evidence sufficiency satisfied ({sufficiency_check['score']:.2f})")
                break

        # Fallback if no chunks accumulated across hops
        if not accumulated_chunks:
            print("⚠️ [MULTI-HOP FALLBACK] No chunks retrieved in iterative hops. Falling back to single-pass.")
            fallback_res = NexusAdvancedRAG.retrieve_hybrid_context(question, filenames, user_id=user_id)
            accumulated_chunks = fallback_res.get("top_chunks", [])
            all_citations = fallback_res.get("citations", [])

        # Sort accumulated chunks by rerank score
        accumulated_chunks.sort(key=lambda x: x.get("rerank_score", x.get("hybrid_score", 0.0)), reverse=True)
        final_chunks = accumulated_chunks[:12]

        # Evaluate final sufficiency and conflicts
        final_sufficiency = VerificationService.verify_evidence_sufficiency(question, final_chunks)
        final_conflicts = VerificationService.detect_cross_document_conflicts(final_chunks)

        # Format context with XML tags and conflict annotations
        from privacy_scanner import PromptInjectionShield
        formatted_context = PromptInjectionShield.wrap_isolated_context(final_chunks)
        if final_conflicts["conflict_detected"]:
            conflict_annotation = VerificationService.format_conflict_grounding_annotation(final_conflicts["conflicts"])
            formatted_context = f"{conflict_annotation}\n\n{formatted_context}"

        elapsed_ms = (time.perf_counter() - t_start) * 1000.0
        print(f"🏁 [MULTI-HOP COMPLETE] Hops={executed_hops}, Chunks={len(final_chunks)}, Sufficiency={final_sufficiency['status']}, Conflict={final_conflicts['conflict_detected']}, Time={elapsed_ms:.1f}ms")
        print("=" * 70)

        return {
            "reasoning_mode": "multi_hop",
            "hop_count": executed_hops,
            "subqueries": subqueries[:executed_hops],
            "top_chunks": final_chunks,
            "formatted_context": formatted_context,
            "evidence_quality": "High" if len(final_chunks) >= 2 else "Medium",
            "evidence_sufficiency": final_sufficiency["status"],
            "sufficiency_details": final_sufficiency,
            "conflict_detected": final_conflicts["conflict_detected"],
            "conflicts": final_conflicts["conflicts"],
            "table_evidence": is_table_query,
            "citations": all_citations,
            "timings": {
                "reasoning_ms": round(elapsed_ms, 2),
                "total_retrieval_ms": round(elapsed_ms, 2),
            },
        }
