"""
NexusAI - Adaptive RAG Optimizer
================================
Intelligent, deterministic, lightweight retrieval strategy layer for NexusAI.
Selects optimal retrieval parameters (weights, top-k, expansion, compression)
without making LLM calls or compromising security/authorization.

Execution Budget: < 5-10ms overhead.
"""

import os
import re
import time
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple


# ============================================================
# CONFIGURATION & ENVIRONMENT
# ============================================================

RAG_OPTIMIZER_ENABLED = os.getenv("RAG_OPTIMIZER_ENABLED", "true").lower() in ("true", "1", "yes")
RAG_OPTIMIZER_MIN_TOP_K = int(os.getenv("RAG_OPTIMIZER_MIN_TOP_K", "8"))
RAG_OPTIMIZER_MAX_TOP_K = int(os.getenv("RAG_OPTIMIZER_MAX_TOP_K", "40"))
RAG_OPTIMIZER_MAX_RERANK_K = int(os.getenv("RAG_OPTIMIZER_MAX_RERANK_K", "40"))


# ============================================================
# STRATEGY DATA STRUCTURE
# ============================================================

@dataclass
class OptimizerStrategy:
    """Encapsulates all adaptive retrieval parameters for a single RAG query."""
    query_type: str
    complexity: str
    query_expansion: bool
    multi_query: bool
    semantic_weight: float
    bm25_weight: float
    initial_top_k: int
    rerank_top_k: int
    final_target_k: int
    compression_level: str
    multi_document: bool
    decision_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Return a clean dictionary representation for debugging and explainability."""
        return {
            "query_type": self.query_type,
            "complexity": self.complexity,
            "query_expansion": self.query_expansion,
            "multi_query": self.multi_query,
            "semantic_weight": round(self.semantic_weight, 3),
            "bm25_weight": round(self.bm25_weight, 3),
            "initial_top_k": self.initial_top_k,
            "rerank_top_k": self.rerank_top_k,
            "final_target_k": self.final_target_k,
            "compression_level": self.compression_level,
            "multi_document": self.multi_document,
            "decision_ms": round(self.decision_ms, 3),
        }


# ============================================================
# ADAPTIVE RAG OPTIMIZER ENGINE
# ============================================================

class AdaptiveRAGOptimizer:
    """
    Lightweight, deterministic retrieval strategy engine.
    Analyzes query characteristics in microseconds and resolves dynamic
    retrieval parameters to maximize recall and precision while minimizing latency.
    """

    # Pre-compiled regex patterns for lightning-fast deterministic matching
    _RE_CODE_IDENTIFIER = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+\b")
    _RE_CAMEL_CASE = re.compile(r"\b[a-z]+[A-Z][a-zA-Z0-9]*\b")
    _RE_ERROR_CODE = re.compile(r"\b(?:ERR_[A-Z0-9_]+|HTTP\s+[1-5]\d{2}|[1-5]\d{2}\s+(?:OK|Found|Unauthorized|Forbidden|Not Found|Error)|Exception|TypeError|ValueError|NullPointer)\b", re.IGNORECASE)
    _RE_CODE_SYMBOLS = re.compile(r"[{}\[\]()<>=+\-*/\\|&^%#@~`]")
    _RE_SHORT_COMPARE = re.compile(r"^(?:both\s+same|same\s+or\s+not|same\s+or\s+different|both\s+similar|same|similar)(?:\s+(?:aa|ah|na|enti))?\??$", re.IGNORECASE)
    _RE_POINT_COUNT = re.compile(r"\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:points?|bullets?|items?)\b", re.IGNORECASE)

    @classmethod
    def classify_query(cls, question: str, filenames: Optional[List[str]] = None) -> Tuple[str, str]:
        """
        Deterministically classify the query into (query_type, complexity).
        Categories:
          - simple_factual
          - exact_keyword_technical
          - conceptual
          - procedural
          - comparison
          - multi_document
          - complex_analytical
          - ambiguous
        Complexity:
          - simple
          - medium
          - complex
        """
        if not question or not question.strip():
            return "ambiguous", "simple"

        q_raw = question.strip()
        q_lower = q_raw.lower()
        words = q_lower.split()
        num_words = len(words)
        filenames_count = len(filenames) if filenames else 0

        # 1. Comparison Queries (Highest precedence for multi-doc reasoning)
        if (
            cls._RE_SHORT_COMPARE.match(q_lower)
            or any(w in q_lower for w in (
                "compare", "comparison", "difference", "differences", "similarity", "similarities",
                "versus", " vs ", "contrast", "differ", "higher than", "lower than", "better than",
                "both documents", "these two", "between doc"
            ))
            or (filenames_count > 1 and any(w in q_lower for w in ("which company", "which document", "which one", "who has higher", "who has lower", "both")))
        ):
            return "comparison", "complex"

        # 2. Exact Keyword & Technical Queries (API symbols, error codes, camelCase, dot-notation)
        has_dot_identifier = bool(cls._RE_CODE_IDENTIFIER.search(q_raw))
        has_camel_case = bool(cls._RE_CAMEL_CASE.search(q_raw))
        has_error_code = bool(cls._RE_ERROR_CODE.search(q_raw))
        has_code_syntax = bool(re.search(r"```|`[^`]+`|\b(?:function|method|endpoint|param|syntax|config|api_key|token|id)\b", q_lower))

        if has_dot_identifier or has_error_code or (has_camel_case and not q_lower.startswith("what is ")) or has_code_syntax:
            complexity = "simple" if num_words <= 6 else "medium"
            return "exact_keyword_technical", complexity

        # 3. Procedural / How-To Queries
        if (
            q_lower.startswith(("how to", "how do i", "how can i", "how should", "steps to", "steps for", "guide to", "procedure for", "process of", "instructions to", "walkthrough"))
            or any(w in q_lower for w in ("installation steps", "step by step", "how to configure", "how to setup", "how to deploy"))
        ):
            return "procedural", "medium"

        # 4. Complex Analytical Queries (multi-part, deep reasoning, trade-offs, causal analysis)
        analytical_triggers = (
            "analyze", "analysis", "evaluate", "evaluation", "impact of", "root cause",
            "trade-offs", "pros and cons", "implications of", "relationship between",
            "explain why and how", "underlying reasons", "synthesis of"
        )
        if any(trig in q_lower for trig in analytical_triggers) or (num_words >= 18 and any(w in q_lower for w in ("because", "furthermore", "consequently", "therefore", "impact", "affect"))):
            return "complex_analytical", "complex"

        # 5. Ambiguous / Extremely Short Vague Query (1-2 words without explicit intent)
        ambiguous_vague_terms = {"notes", "help", "doc", "data", "info", "test", "details", "misc", "content", "stuff"}
        if (
            q_lower in ambiguous_vague_terms
            or (
                num_words <= 2
                and not any(q_lower.startswith(w) for w in ("what", "who", "when", "where", "how", "why", "is", "are", "tell", "give", "show"))
                and not any(w in q_lower for w in ("summary", "summarize", "overview", "explain", "describe", "compare", "definition"))
            )
        ):
            return "ambiguous", "simple"

        # 6. Conceptual Queries (definitions, architecture, theory, high-level overview/summary)
        conceptual_triggers = (
            "what is this document about", "tell me about this", "describe this document",
            "explain the document", "summary", "summarize", "overview", "core concept",
            "architecture", "philosophy", "design principle", "meaning of", "definition of",
            "explain the idea", "what does it mean", "high level overview"
        )
        if any(w in q_lower for w in conceptual_triggers) or q_lower.startswith(("explain ", "describe ", "what is the concept", "what are the principles")):
            return "conceptual", "medium"

        # 7. Explicit Multi-Document query without comparison keyword
        if filenames_count > 1 and ("across" in q_lower or "all documents" in q_lower or "both" in q_lower):
            return "multi_document", "complex"

        # 8. Simple Factual (default standard lookup)
        # Direct questions: "What is Company A's revenue?", "Who is the CEO?", "When was X founded?", etc.
        return "simple_factual", "simple"

    @classmethod
    def resolve_strategy(
        cls,
        question: str,
        filenames: Optional[List[str]] = None,
        user_id: Optional[int] = None,
    ) -> OptimizerStrategy:
        """
        Generate optimal retrieval parameters based on query classification,
        document count, and environment constraints.
        """
        t0 = time.time()
        file_list = filenames or []
        doc_count = len(file_list)
        is_multi_doc = doc_count > 1
        q_raw = (question or "").strip()
        num_words = len(q_raw.split())

        # Determine query classification
        qtype, complexity = cls.classify_query(question, file_list)

        # Baseline parameters per category
        if qtype == "exact_keyword_technical":
            # Lexical / BM25 emphasis for exact code symbols, error codes, endpoints
            semantic_w = 0.35
            bm25_w = 0.65
            query_expansion = False
            multi_query = False
            base_top_k = 10 if complexity == "simple" else 15
            base_rerank_k = 12 if complexity == "simple" else 18
            final_k = 6
            compression = "standard"

        elif qtype == "conceptual":
            # Semantic emphasis for abstract concepts, summaries, high-level overviews
            semantic_w = 0.70
            bm25_w = 0.30
            # For descriptive conceptual queries, full sentence vector representation is optimal
            # Enable expansion only on short/vague conceptual prompts (< 6 words)
            query_expansion = num_words < 6
            multi_query = False
            base_top_k = 15
            base_rerank_k = 16
            final_k = 8
            compression = "standard"

        elif qtype == "procedural":
            # Balanced search with standard expansion for sequential steps
            semantic_w = 0.55
            bm25_w = 0.45
            query_expansion = True
            multi_query = False
            base_top_k = 15
            base_rerank_k = 16
            final_k = 8
            compression = "standard"

        elif qtype == "comparison":
            # Targeted entity multi-query enabled, balanced broad candidate pool
            semantic_w = 0.60
            bm25_w = 0.40
            query_expansion = True
            multi_query = True
            base_top_k = 24
            base_rerank_k = 24
            final_k = 6 * max(1, doc_count)
            compression = "broad"

        elif qtype == "complex_analytical":
            # Targeted multi-query enabled, deeper candidate exploration with broad context
            semantic_w = 0.65
            bm25_w = 0.35
            query_expansion = True
            multi_query = True
            base_top_k = 20
            base_rerank_k = 20
            final_k = 8
            compression = "broad"

        elif qtype == "multi_document":
            # Global multi-doc retrieval across authorized corpus
            semantic_w = 0.60
            bm25_w = 0.40
            query_expansion = True
            multi_query = True
            base_top_k = 25
            base_rerank_k = 25
            final_k = 6 * max(1, doc_count)
            compression = "broad"

        elif qtype == "ambiguous":
            # Expansion on to disambiguate short inputs
            semantic_w = 0.60
            bm25_w = 0.40
            query_expansion = True
            multi_query = False
            base_top_k = 12
            base_rerank_k = 15
            final_k = 6
            compression = "standard"

        else:  # simple_factual
            # Fast, direct retrieval without costly multi-query expansion
            semantic_w = 0.50
            bm25_w = 0.50
            query_expansion = False
            multi_query = False
            base_top_k = 10
            base_rerank_k = 12
            final_k = 6
            compression = "strict"

        # Multi-document pool scaling with safe upper bounds
        if is_multi_doc:
            scaling_factor = min(doc_count, 3)
            base_top_k = max(base_top_k, 12 * scaling_factor)
            base_rerank_k = max(base_rerank_k, 15 * scaling_factor)
            if qtype not in ("comparison", "complex_analytical", "multi_document"):
                compression = "broad"

        # Apply safe bounds
        initial_top_k = max(RAG_OPTIMIZER_MIN_TOP_K, min(RAG_OPTIMIZER_MAX_TOP_K, base_top_k))
        rerank_top_k = max(RAG_OPTIMIZER_MIN_TOP_K, min(RAG_OPTIMIZER_MAX_RERANK_K, base_rerank_k))

        elapsed_ms = (time.time() - t0) * 1000.0

        return OptimizerStrategy(
            query_type=qtype,
            complexity=complexity,
            query_expansion=query_expansion,
            multi_query=multi_query,
            semantic_weight=semantic_w,
            bm25_weight=bm25_w,
            initial_top_k=initial_top_k,
            rerank_top_k=rerank_top_k,
            final_target_k=final_k,
            compression_level=compression,
            multi_document=is_multi_doc,
            decision_ms=elapsed_ms,
        )

    @classmethod
    def get_default_strategy(cls, filenames: Optional[List[str]] = None) -> OptimizerStrategy:
        """Safe fallback strategy matching the existing static RAG configuration."""
        doc_count = len(filenames) if filenames else 0
        is_multi = doc_count > 1
        return OptimizerStrategy(
            query_type="default_fallback",
            complexity="medium",
            query_expansion=True,
            multi_query=is_multi,
            semantic_weight=float(os.getenv("RAG_SEMANTIC_WEIGHT", "0.6")),
            bm25_weight=float(os.getenv("RAG_LEXICAL_WEIGHT", "0.4")),
            initial_top_k=int(os.getenv("RAG_INITIAL_K", "30")),
            rerank_top_k=30,
            final_target_k=int(os.getenv("RAG_FINAL_K", "8")),
            compression_level="standard",
            multi_document=is_multi,
            decision_ms=0.0,
        )

    @classmethod
    def optimize(
        cls,
        question: str,
        filenames: Optional[List[str]] = None,
        user_id: Optional[int] = None,
    ) -> OptimizerStrategy:
        """
        Main entry point for Adaptive RAG optimization.
        Guarantees non-throwing behavior with transparent fallback.
        """
        if not RAG_OPTIMIZER_ENABLED:
            return cls.get_default_strategy(filenames)

        try:
            return cls.resolve_strategy(question, filenames, user_id=user_id)
        except Exception as exc:
            # Safe non-throwing fallback
            print(f"⚠️ [RAG OPTIMIZER FALLBACK] Error evaluating strategy: {exc}. Reverting to static defaults.")
            return cls.get_default_strategy(filenames)
