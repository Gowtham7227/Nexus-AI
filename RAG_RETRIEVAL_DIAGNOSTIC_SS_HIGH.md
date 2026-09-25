# NexusAI — Document RAG Retrieval Diagnostic Report for `ss-high (1).pdf`

**Date**: September 21, 2026
**Canonical Project Root**: `C:\Users\gowth\OneDrive\Desktop\Projects\NexusAI`
**Target Document**: `ss-high (1).pdf` (45,249,259 bytes)
**Registered User**: `user_id = 2` (`chinnunani3117@gmail.com`)
**Investigated Queries**:
1. *"What is the difference between gas giants and ice giants?"*
2. *"What is the heliosphere?"*

---

## 1. Executive Diagnostic Finding & Primary Root Cause

### **Primary Root Cause: (F) Indexing / Vector Store Desynchronization**

| Diagnostic Dimension | Status | Evidence |
|:---|:---:|:---|
| **Physical File Presence** | **EXISTS** | File exists at `uploads/ss-high (1).pdf` (45.2 MB). |
| **Database Record (`auth.db`)** | **PRESENT** | Row `(2, 2, 'ss-high (1).pdf', ..., 'completed', None, 'indexed', ...)` indicates successful historical upload for user 2. |
| **Target Text in Raw PDF** | **PRESENT** | Both concepts exist prominently in the PDF text on Page 4 (and Pages 22, 32, 34, 42). |
| **Native Text Extraction** | **PASS** | 142,654 characters extracted across all 42 pages in ~220 ms. |
| **Chroma DB Index Status** | **MISSING (0 Chunks)** | `chroma_db` currently contains 105 total vectors, **ALL 105 belonging to `electronics-15-00334.pdf`**. Exactly **0 vectors exist in Chroma for `ss-high (1).pdf`**. |
| **BM25 In-Memory Index** | **EMPTY (0 Chunks)** | BM25 is built dynamically from `get_document_chunks()`, which queried Chroma and received `[]`. |
| **Pipeline Retrieval Execution** | **EMPTY CONTEXT** | With 0 vectors in Chroma, retrieval returns empty context `""`, triggering the UI fallback: *"I couldn't find relevant information in the selected document(s)."* |

---

## 2. Document & Database Verification

- **Local Path**: `C:\Users\gowth\OneDrive\Desktop\Projects\NexusAI\uploads\ss-high (1).pdf`
- **File Size**: 45,249,259 bytes (~43.15 MB)
- **Database Record in `auth.db` (`documents` table)**:
  - `id`: `2`
  - `user_id`: `2` (`chinnunani3117@gmail.com`)
  - `filename`: `ss-high (1).pdf`
  - `processing_status`: `completed`
  - `vector_status`: `indexed`
  - `created_at`: `2026-09-14 09:02:45`
  - `extraction_method`: `native`
  - `ocr_used`: `0`
- **Chroma Database Inspection**:
  - Persist Directory: `C:\Users\gowth\OneDrive\Desktop\Projects\NexusAI\chroma_db`
  - Total Chunks in Chroma: **105**
  - Chunks for `ss-high (1).pdf` (user_id 2): **0**
  - Chunks for `ss-high (1).pdf` (any user): **0**
  - Chunks for `electronics-15-00334.pdf`: **105**

---

## 3. Text Extraction & Source Evidence Verification

Native PDF text extraction (`pypdf`) successfully parsed all 42 pages without errors.

### Question 1 Target Terms:
- `'gas giant'`: 3 occurrences (Pages 4, 42)
- `'ice giant'`: 6 occurrences (Pages 4, 22, 32, 34, 42)
- `'jupiter'`: 94 occurrences (Pages 1, 3, 4, 10, 18, 22, 23, 24, 25, 26...)
- `'saturn'`: 93 occurrences (Pages 1, 3, 4, 10, 22, 24, 27, 28, 29, 30...)
- `'uranus'`: 58 occurrences (Pages 1, 3, 4, 22, 28, 31, 32, 34, 36, 42)
- `'neptune'`: 59 occurrences (Pages 1, 3, 4, 22, 28, 32, 33, 34, 36, 38...)
- `'composition'`: 10 occurrences (Pages 4, 6, 18, 20, 24, 34, 36, 38)
- `'hydrogen'`: 13 occurrences; `'helium'`: 10 occurrences; `'methane'`: 12 occurrences

**Key Source Excerpts**:
> **Page 4**: *"Jupiter and Saturn — are known as gas giants; the more distant Uranus and Neptune are called ice giants."*
> **Page 32**: *"Uranus is one of the two ice giants of the outer solar system (the other is Neptune). The atmosphere is mostly hydrogen and helium, with a small amount of methane and traces of water and ammonia... bulk (80 percent or more) of the mass of Uranus is contained in an extended liquid core consisting mostly of icy materials (water, methane, and ammonia)."*
> **Page 24 & 28**: Jupiter and Saturn gas giants consisting predominantly of hydrogen and helium gas.

### Question 2 Target Terms:
- `'heliosphere'`: 3 occurrences (Page 4)
- `'solar wind'`: 14 occurrences (Pages 4, 6, 8, 12, 14, 24, 28, 38)
- `'sun'`: 156 occurrences (Pages 1, 4, 5, 6, 8, 10, 12, 16, 18, 20...)
- `'solar system'`: 56 occurrences (Pages 3, 4, 6, 8, 12, 16, 18, 20, 21, 22...)

**Key Source Excerpt**:
> **Page 4**: *"The area of the Sun's influence stretches far beyond the planets, forming a giant bubble called the heliosphere. The enormous bubble of the heliosphere is created by the solar wind, a stream of charged gas blowing outward from the Sun. As the Sun orbits the center of the Milky Way, the bubble of the heliosphere moves also, creating a bow shock ahead of itself in interstellar space — like the bow of a ship in water — as it crashes into the interstellar gases. The area where the solar wind is abruptly slowed by pressure from gas..."*

---

## 4. End-to-End Pipeline Tracing (Simulated with Re-Indexed Document)

When `ss-high (1).pdf` is chunked (225 chunks) and indexed, the entire retrieval pipeline operates as follows:

```
Question ──► Authorization (user_id=2) ──► Adaptive Optimizer ──► Query Expander ──► Chroma (Semantic) + BM25 (Lexical) ──► Hybrid Fusion ──► Cross-Encoder Reranker ──► Final Context
```

### Trace A: Question 1 — *"What is the difference between gas giants and ice giants?"*

1. **Optimizer Decision** (Latency: `0.037 ms`):
   - Query Type: `comparison`
   - Complexity: `complex`
   - Query Expansion: `True` (Multi-Query: `True`)
   - Semantic Weight: `0.60` | BM25 Weight: `0.40`
   - Initial Top-K: `24` | Rerank Top-K: `24`
   - Compression Mode: `broad`
2. **Query Expansion** (3 variants generated):
   - Variant 1: `"What is the difference between gas giants and ice giants?"`
   - Variant 2: `"difference between gas giants and ice giants"`
   - Variant 3: `"difference gas giants ice giants comparison difference"`
3. **Chroma Semantic Retrieval**:
   - 24 candidates retrieved across 3 queries.
   - Top candidates include Chunk 13 (Page 4, score `0.4094`) and Chunk 169 (Page 32, score `0.3812`).
4. **BM25 Lexical Retrieval**:
   - Top candidate: Chunk 13 (Page 4), BM25 score = `20.2636` (exact match for "gas giants", "ice giants", "difference").
5. **Hybrid Fusion (RRF / Weighted)**:
   - Rank 1: Chunk 13 (Page 4) — Hybrid Score: `0.6457` (BM25: `1.0000`, Sem: `0.4094`).
6. **Cross-Encoder Reranking (`ms-marco-MiniLM-L-6-v2`)**:
   - **Rank 1**: Chunk 13 (Page 4) — **Cross-Encoder Score: `0.9832`** $\to$ **Final Weighted Score: `0.8819`**.
   - Snippet: *"Jupiter and Saturn — are known as gas giants; the more distant Uranus and Neptune are called ice giants..."*
7. **Final Context**:
   - 8 chunks selected; ground-truth distinction between gas giants and ice giants is present at **Rank #1**.

---

### Trace B: Question 2 — *"What is the heliosphere?"*

1. **Optimizer Decision** (Latency: `0.383 ms`):
   - Query Type: `simple_factual`
   - Complexity: `simple`
   - Query Expansion: `False` (Multi-Query: `False`)
   - Semantic Weight: `0.50` | BM25 Weight: `0.50`
   - Initial Top-K: `10` | Rerank Top-K: `12`
   - Compression Mode: `strict`
2. **Query Expansion**:
   - Single targeted query: `"What is the heliosphere?"`
3. **Chroma Semantic Retrieval**:
   - 10 candidates retrieved.
   - Chunk 16 (Page 4) retrieved with score `0.2907`.
4. **BM25 Lexical Retrieval**:
   - Top candidate: Chunk 16 (Page 4), BM25 score = `7.6288` (exact match on "heliosphere").
5. **Hybrid Fusion**:
   - **Rank 1**: Chunk 16 (Page 4) — Hybrid Score: `0.6454` (BM25: `1.0000`, Sem: `0.2907`).
6. **Cross-Encoder Reranking**:
   - **Rank 1**: Chunk 16 (Page 4) — **Cross-Encoder Score: `0.9987`** $\to$ **Final Weighted Score: `0.8927`**.
   - Snippet: *"called the heliosphere. The enormous bubble of the heliosphere is created by the solar wind, a stream of charged gas blowing outward from the Sun..."*
7. **Final Context**:
   - Ground-truth definition of the heliosphere is present at **Rank #1**.

---

## 5. Question Comparison Matrix

| Question | Source Evidence in PDF | Chroma Index Status | BM25 Status | Hybrid Fusion | Cross-Encoder Rank | Final Context | Live Browser Result |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Q1: Gas vs Ice Giants** | **Yes (Pages 4, 32, 42)** | 0 chunks currently | 0 chunks currently | 0 chunks | N/A (Empty) | Empty (`""`) | `"I couldn't find relevant info..."` |
| **Q1 (Simulated Index)** | **Yes (Pages 4, 32, 42)** | 24 hits (Chunk 13 top) | Score 20.26 (#1) | Score 0.6457 (#1) | **Score 0.9832 (#1)** | **Found at Rank #1** | **Answerable** |
| **Q2: Heliosphere** | **Yes (Page 4)** | 0 chunks currently | 0 chunks currently | 0 chunks | N/A (Empty) | Empty (`""`) | `"I couldn't find relevant info..."` |
| **Q2 (Simulated Index)** | **Yes (Page 4)** | 10 hits (Chunk 16) | Score 7.62 (#1) | Score 0.6454 (#1) | **Score 0.9987 (#1)** | **Found at Rank #1** | **Answerable** |

---

## 6. Threshold & Regression Audit

1. **Threshold Assessment**:
   - Relevance / Similarity thresholds are not filtering out chunks; Cross-Encoder scores for the relevant chunks are `0.9832` and `0.9987` (near 1.0).
   - In both cases, the target chunks easily rank #1 in the final candidate pool.
2. **Adaptive RAG Optimizer Regression Check**:
   - **Optimizer ENABLED vs DISABLED**: Both enabled and disabled modes identify the identical top chunks at Rank #1.
   - The Adaptive Optimizer achieves faster execution for Q2 (`simple_factual`, 10 top-k, strict compression) and broader candidate coverage for Q1 (`comparison`, 24 top-k).
   - **Conclusion**: The optimizer did **not** cause the retrieval failure.

---

## 7. Failure Origin & Recommended Resolution

### Exact Failure Origin
During repository consolidation or previous test executions, the SQLite database `auth.db` was preserved with historical records (showing `ss-high (1).pdf` with `status='completed'`, `vector_status='indexed'`), while `chroma_db` (which is gitignored) was newly initialized or contained only recent files (`electronics-15-00334.pdf`).

Because Chroma had no vector embeddings for `ss-high (1).pdf`:
1. `NexusAdvancedRAG.get_document_chunks("ss-high (1).pdf", user_id=2)` returned `[]`.
2. BM25 received 0 chunks.
3. Chroma similarity search filtered by `{"filename": "ss-high (1).pdf"}` returned 0 chunks.
4. Total retrieved context was empty (`""`).
5. The API returned `"I couldn't find relevant information in the selected document(s)."`.

### Recommended Fix (When Approved)
1. **Re-index `ss-high (1).pdf`**: Run `create_vector_store` for `ss-high (1).pdf` using its existing physical file in `uploads/ss-high (1).pdf` with `user_id=2`.
2. **Self-Healing / Re-Index Guard**: In `get_document_chunks()` or during document selection in `main.py`, if a document is marked `vector_status='indexed'` in SQLite but Chroma returns 0 chunks, automatically trigger background re-indexing from the physical file in `uploads/`.
