"""
NexusAI v1.4 - Evidence Sufficiency Verification & Conflict Detection
=====================================================================
Analyzes retrieved multi-document evidence pools to:
1. Verify evidence sufficiency prior to LLM generation (detects gaps / unanswerable queries).
2. Identify cross-document factual contradictions (e.g. opposing numbers, dates, policies).
3. Attribute conflicting claims to exact sources without arbitrarily picking a winner.
"""

import re
from typing import List, Dict, Any, Optional, Tuple


class VerificationService:
    """
    Evaluates evidence sufficiency and detects cross-document factual contradictions.
    """

    # Numbers with units/symbols: $10M, 25%, 4 hours, 2026, etc.
    _RE_NUMERICAL_FACT = re.compile(
        r"(?:[\$\€\£]?\d+(?:\.\d+)?\s*(?:million|billion|trillion|percent|%|USD|EUR|GB|TB|MB|kW|MW|GW|hours?|days?|years?|employees?|dollars?|USD)?)\b",
        re.IGNORECASE
    )

    # Opposing polarity terms
    _OPPOSING_POLARITY_PAIRS = [
        ("increase", "decrease"),
        ("increased", "decreased"),
        ("rise", "fall"),
        ("rose", "fell"),
        ("passed", "failed"),
        ("passed", "rejected"),
        ("approved", "rejected"),
        ("approved", "denied"),
        ("mandatory", "optional"),
        ("prohibited", "allowed"),
        ("authorized", "unauthorized"),
        ("higher", "lower"),
        ("more", "less"),
        ("exceeded", "below"),
    ]

    @classmethod
    def verify_evidence_sufficiency(
        cls,
        question: str,
        chunks: List[Dict[str, Any]],
        relevance_threshold: float = 0.25,
    ) -> Dict[str, Any]:
        """
        Determine whether retrieved evidence contains sufficient factual grounding
        to answer the user query.
        Returns:
          {
            "status": "sufficient" | "partial" | "insufficient",
            "score": float (0.0 to 1.0),
            "matched_terms": List[str],
            "missing_terms": List[str],
            "high_quality_chunks": int,
          }
        """
        if not chunks:
            return {
                "status": "insufficient",
                "score": 0.0,
                "matched_terms": [],
                "missing_terms": [],
                "high_quality_chunks": 0,
            }

        q_clean = question.strip().lower()
        stopwords = {
            "what", "who", "where", "when", "why", "how", "is", "are", "was", "were",
            "the", "a", "an", "and", "or", "in", "on", "of", "to", "for", "with",
            "from", "by", "about", "tell", "me", "give", "show", "explain", "does", "did", "do",
            "compare", "comparison", "difference", "differences", "versus", "vs", "between",
            "count", "list", "detail", "details", "summary", "overview", "report"
        }
        tokens = [w for w in re.findall(r"\b[a-z0-9_]{2,}\b", q_clean) if w not in stopwords]

        if not tokens:
            return {
                "status": "sufficient",
                "score": 1.0,
                "matched_terms": [],
                "missing_terms": [],
                "high_quality_chunks": len(chunks),
            }

        # Combine text of relevant chunks
        combined_text = " ".join(c.get("text", "").lower() for c in chunks)

        def _term_in_text(term: str, text: str) -> bool:
            if term in text:
                return True
            root = term.rstrip("s").rstrip("es").rstrip("ed").rstrip("ing")
            if len(root) >= 4 and root in text:
                return True
            for word in re.findall(r"\b[a-z0-9_]{3,}\b", text):
                if (len(root) >= 4 and word.startswith(root)) or (len(word) >= 4 and root.startswith(word)):
                    return True
            return False

        matched_terms = [t for t in tokens if _term_in_text(t, combined_text)]
        missing_terms = [t for t in tokens if not _term_in_text(t, combined_text)]

        term_coverage = len(matched_terms) / len(tokens) if tokens else 1.0

        # Count chunks that meet relevance score threshold
        high_quality_chunks = 0
        for c in chunks:
            score = c.get("rerank_score", c.get("hybrid_score", c.get("score", 0.0)))
            if score >= relevance_threshold:
                high_quality_chunks += 1

        if term_coverage >= 0.65 and high_quality_chunks >= 1:
            status = "sufficient"
        elif term_coverage >= 0.35 or high_quality_chunks >= 1:
            status = "partial"
        else:
            status = "insufficient"

        return {
            "status": status,
            "score": round(term_coverage, 3),
            "matched_terms": matched_terms,
            "missing_terms": missing_terms,
            "high_quality_chunks": high_quality_chunks,
        }

    @classmethod
    def detect_cross_document_conflicts(
        cls,
        chunks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Scan chunks from distinct document sources to detect direct numerical
        or polarity contradictions on common subjects.
        Returns:
          {
            "conflict_detected": bool,
            "conflicts": List[Dict[str, Any]],
          }
        """
        if not chunks or len(chunks) < 2:
            return {"conflict_detected": False, "conflicts": []}

        # Group chunks by source filename
        doc_chunks: Dict[str, List[Dict[str, Any]]] = {}
        for c in chunks:
            source = c.get("metadata", {}).get("filename") or c.get("filename") or c.get("source", "unknown")
            doc_chunks.setdefault(source, []).append(c)

        # If all chunks are from a single document, no cross-document conflict
        if len(doc_chunks) < 2:
            return {"conflict_detected": False, "conflicts": []}

        sources = list(doc_chunks.keys())
        conflicts = []

        # Compare pairs of distinct documents
        for i in range(len(sources)):
            for j in range(i + 1, len(sources)):
                src_a = sources[i]
                src_b = sources[j]
                text_a = " ".join(c.get("text", "") for c in doc_chunks[src_a])
                text_b = " ".join(c.get("text", "") for c in doc_chunks[src_b])

                # 1. Check opposing polarity keywords in overlapping topics
                polarity_conflict = cls._check_polarity_conflicts(text_a, text_b, src_a, src_b)
                if polarity_conflict:
                    conflicts.extend(polarity_conflict)

                # 2. Check differing numerical facts on common entity topics
                numerical_conflict = cls._check_numerical_conflicts(text_a, text_b, src_a, src_b)
                if numerical_conflict:
                    conflicts.extend(numerical_conflict)

        # Deduplicate conflicts
        seen_keys = set()
        unique_conflicts = []
        for conf in conflicts:
            key = (conf.get("topic"), conf.get("source_a"), conf.get("source_b"))
            if key not in seen_keys:
                seen_keys.add(key)
                unique_conflicts.append(conf)

        return {
            "conflict_detected": len(unique_conflicts) > 0,
            "conflicts": unique_conflicts,
        }

    @classmethod
    def _check_polarity_conflicts(
        cls,
        text_a: str,
        text_b: str,
        src_a: str,
        src_b: str,
    ) -> List[Dict[str, Any]]:
        """Identify if Doc A asserts X while Doc B asserts opposing Y."""
        lower_a = text_a.lower()
        lower_b = text_b.lower()
        conflicts = []

        for pos, neg in cls._OPPOSING_POLARITY_PAIRS:
            if (pos in lower_a and neg in lower_b) or (neg in lower_a and pos in lower_b):
                # Extract sentence context
                claim_a = cls._extract_sentence_with_term(text_a, pos if pos in lower_a else neg)
                claim_b = cls._extract_sentence_with_term(text_b, neg if neg in lower_b else pos)
                conflicts.append({
                    "type": "polarity_contradiction",
                    "topic": f"{pos} vs {neg}",
                    "source_a": src_a,
                    "claim_a": claim_a,
                    "source_b": src_b,
                    "claim_b": claim_b,
                    "description": f"Source '{src_a}' asserts '{pos}' while '{src_b}' asserts '{neg}'."
                })

        return conflicts

    @classmethod
    def _check_numerical_conflicts(
        cls,
        text_a: str,
        text_b: str,
        src_a: str,
        src_b: str,
    ) -> List[Dict[str, Any]]:
        """Identify if Doc A and Doc B state differing metrics for the same attribute (e.g. revenue, budget, cost)."""
        metrics = ["revenue", "budget", "cost", "headcount", "employees", "profit", "loss", "growth", "conversion efficiency", "storage"]
        lower_a = text_a.lower()
        lower_b = text_b.lower()
        conflicts = []

        for metric in metrics:
            if metric in lower_a and metric in lower_b:
                sent_a = cls._extract_sentence_with_term(text_a, metric)
                sent_b = cls._extract_sentence_with_term(text_b, metric)

                nums_a = cls._RE_NUMERICAL_FACT.findall(sent_a)
                nums_b = cls._RE_NUMERICAL_FACT.findall(sent_b)

                if nums_a and nums_b:
                    # Filter and compare numbers, excluding shared 4-digit year timestamps
                    val_a = {n.strip().lower() for n in nums_a if n.strip()}
                    val_b = {n.strip().lower() for n in nums_b if n.strip()}

                    # Shared years like 2026 should not prevent detecting differences in monetary/metric figures
                    diff_a = {v for v in val_a if not (re.match(r"^(19|20)\d\d$", v) and v in val_b)}
                    diff_b = {v for v in val_b if not (re.match(r"^(19|20)\d\d$", v) and v in val_a)}

                    if diff_a and diff_b and (diff_a != diff_b):
                        conflicts.append({
                            "type": "numerical_discrepancy",
                            "topic": metric,
                            "source_a": src_a,
                            "claim_a": sent_a,
                            "value_a": list(diff_a),
                            "source_b": src_b,
                            "claim_b": sent_b,
                            "value_b": list(diff_b),
                            "description": f"Different numerical values reported for '{metric}': {list(diff_a)} ({src_a}) vs {list(diff_b)} ({src_b})."
                        })

        return conflicts

        return conflicts

    @classmethod
    def _extract_sentence_with_term(cls, text: str, term: str) -> str:
        """Find the sentence containing the target term."""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        for s in sentences:
            if term.lower() in s.lower():
                return s.strip()
        return text[:150].strip()

    @classmethod
    def format_conflict_grounding_annotation(cls, conflicts: List[Dict[str, Any]]) -> str:
        """Format conflict metadata into structured grounding XML tags for the LLM."""
        if not conflicts:
            return ""

        lines = ["<cross_document_conflicts>"]
        for idx, conf in enumerate(conflicts, start=1):
            lines.append(
                f'  <conflict id="{idx}" topic="{conf.get("topic")}" type="{conf.get("type")}">'
            )
            lines.append(f'    <source name="{conf.get("source_a")}">"{conf.get("claim_a")}"</source>')
            lines.append(f'    <source name="{conf.get("source_b")}">"{conf.get("claim_b")}"</source>')
            lines.append(f'    <instruction>Note: Sources disagree on {conf.get("topic")}. Explicitly present both perspectives with citations instead of arbitrarily picking one.</instruction>')
            lines.append("  </conflict>")
        lines.append("</cross_document_conflicts>")
        return "\n".join(lines)
