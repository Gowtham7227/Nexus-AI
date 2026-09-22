# NexusAI — RAG Quality & Grounding Evaluation Report

**Evaluation Timestamp**: `2026-09-21T17:59:37Z`  
**Dataset**: `NexusAI Deterministic RAG Evaluation Benchmark` (v1.0.0)  
**Optimizer Enabled**: `True`  
**Total Test Cases**: `10`  

---

## 1. Global Benchmark Summary

| Metric | Result | Description |
|:---|:---:|:---|
| **Mean Hit@5** | **100.0%** | Proportion of queries with expected source in top 5 chunks |
| **Mean MRR** | **1.0000** | Mean Reciprocal Rank of first relevant source chunk |
| **Mean Grounding Score** | **40.0%** | Sentence-level claim support against retrieved evidence |
| **Citation Correctness** | **100.0%** | Proportion of citations referencing verified retrieved sources |
| **Mean Latency** | **3685.67 ms** | Average total retrieval and evaluation duration |

---

## 2. Category Performance Breakdown

| Category | Cases | Hit@5 | MRR | Grounding | Citation | Avg Latency |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Simple Factual** | 1 | 100.0% | 1.0000 | 0.0% | 100.0% | 16475.9 ms |
| **Exact Technical** | 1 | 100.0% | 1.0000 | 0.0% | 100.0% | 87.3 ms |
| **Conceptual** | 1 | 100.0% | 1.0000 | 0.0% | 100.0% | 84.1 ms |
| **Procedural** | 1 | 100.0% | 1.0000 | 0.0% | 100.0% | 79.3 ms |
| **Comparison** | 1 | 100.0% | 1.0000 | 100.0% | 100.0% | 14296.4 ms |
| **Multi Document** | 1 | 100.0% | 1.0000 | 0.0% | 100.0% | 529.2 ms |
| **Complex Analytical** | 1 | 100.0% | 1.0000 | 0.0% | 100.0% | 111.1 ms |
| **Ambiguous Insufficient** | 1 | 100.0% | 1.0000 | 100.0% | 100.0% | 97.4 ms |
| **Ocr Derived** | 1 | 100.0% | 1.0000 | 100.0% | 100.0% | 57.7 ms |
| **Page Specific** | 1 | 100.0% | 1.0000 | 100.0% | 100.0% | 5038.1 ms |

---

## 3. Grounding & Citation Validation Rules

- **Deterministic Evaluation**: Sentence-level n-gram overlap against trusted server-side chunks (no secondary LLM hallucination).
- **Zero Injection Risk**: Citation IDs originate exclusively from server-side retrieval structures, ignoring any text-injected citation markers.
- **Self-Healing Compatibility**: If vectors are missing for an indexed document, retrieval returns empty context safely without fabricating citations.
