# NexusAI v1.4.0 - Privacy-Aware Advanced RAG & Research Document Intelligence Platform

NexusAI is an enterprise-grade, privacy-aware **Advanced Retrieval-Augmented Generation (RAG)** platform for document intelligence, semantic search, multi-document reasoning, multi-hop evidence synthesis, and structured data analysis supporting documents up to **100 MB**.

---

## 🌟 Key Capabilities & Features in v1.4.0

### 🔬 Core Research Capabilities (v1.4)
- **Bounded Multi-Hop & Iterative Retrieval Engine**:
  - **Dynamic Sub-Query Decomposition**: Deconstructs multi-entity and comparison questions into sequential reasoning hops.
  - **Context-Aware Cross-Hop Bridging**: Injects intermediate retrieved entities into subsequent retrieval iterations.
  - **Context Explosion Bounding**: Strictly caps retrieval iterations (max 3 hops) and token budgets with deterministic early stopping upon evidence sufficiency.
- **Evidence Sufficiency Verification**:
  - **Aspect-Level Coverage Analysis**: Deterministic token and concept coverage evaluation against query requirements.
  - **Missing Evidence Detection**: Explicitly identifies unsupported sub-claims or missing documents before generation.
  - **Hallucination Suppression**: Automatically triggers conservative fallback answering when evidence sufficiency falls below threshold (< 0.60).
- **Cross-Document Conflict Detection**:
  - **Assertion & Entity Extraction**: Identifies numeric values, dates, percentages, and factual claims across multiple ingested documents.
  - **Contradiction Flagging**: Detects cross-source discrepancies and annotates conflicting findings directly in the response metadata.
  - **Confidence Calibration**: Automatically reduces overall answer confidence when unresolved source conflicts exist.
- **Table-Aware Structural Retrieval**:
  - **Grid & Table Parsing**: Converts structured tabular data into high-fidelity Markdown and CSV representations with page-level spatial coordinates.
  - **Schema-Aware Cell Retrieval**: Preserves row-column relationships and header contexts during chunking to prevent fragmented numerical data.

### ⚡ Core RAG & Modular Architecture (v1.3 & v1.2)
- **Fully Modular Fast-API Architecture**:
  - Clear separation of concerns: `routers/`, `services/`, `schemas/`, `dependencies/`, preserving 35/35 REST API endpoints.
  - Ultra-lean application lifecycle (`main.py` ~ 100 lines) with complete route preservation.
- **Adaptive RAG Optimizer**:
  - **Dynamic Strategy Selection**: Rule-based query classifier (factual, technical, conceptual, procedural, comparison, multi-document, analytical, OCR-derived).
  - **Dynamic Parameter Tuning**: Context-aware retrieval depth (Initial K: 15–40, Final K: 3–10), fusion weights (RRF vs. Convex), cross-encoder boost factors.
- **Advanced Multi-Stage RAG Pipeline**:
  - **Hybrid Retrieval**: Dual-stream semantic vector retrieval (ChromaDB + Sentence Transformers `all-MiniLM-L6-v2`) and lexical retrieval (tokenized BM25Okapi).
  - **Self-Healing Vector Fallback**: In-memory dense cosine similarity fallback to prevent query drops during Chroma SQLite desync or lock contention.
  - **Score Fusion**: Reciprocal Rank Fusion (RRF) and Convex Linear Combination for balanced recall across dense and sparse spaces.
  - **True Transformer Cross-Encoder Reranker**: Deep query-document joint attention scoring via `cross-encoder/ms-marco-MiniLM-L-6-v2` executed locally in-process.
  - **Context Expansion & Compression**: Sliding-window context retrieval with redundancy deduplication and token budget optimization.
- **Enterprise Document Processing & OCR**:
  - Native multi-format extraction for PDF, DOCX, and TXT with per-page metadata tracking.
  - **Selective Scanned PDF OCR**: Automatic fallback to Tesseract OCR engine for scanned, image-only, or low-text PDF pages at 300 DPI.
  - 100 MB file upload limit with strict MIME and filename traversal security guards.
- **Privacy & Security Architecture**:
  - **Multi-Tenant User Isolation**: Strict SQL and vector database boundary filtering per `user_id`.
  - **Prompt Injection Defense**: Multi-layer detection and neutralization of jailbreaks, role overriding, and XML boundary escaping.
  - **Output Privacy & PII Guard**: Automated real-time regex sanitization of SSNs, emails, credit cards, and Google API keys.
  - **Right-to-Forget**: Complete cascaded document and vector embedding deletion.
- **Real-Time Streaming & Dual AI Providers**:
  - **Real-Time Streaming**: Server-Sent Events (SSE) via `/chat/stream` (Document RAG) and `/chat/general/stream` (General Assistant).
  - **Cloud LLM**: Google Gemini API (`gemini-3.6-flash` / `gemini-3.5-flash-lite` / `gemini-2.5-flash`) with automatic fallback chains.
  - **Local LLM**: In-process / offline Qwen model via Ollama with automatic fallback.
- **Enterprise Authentication & Session Management**:
  - JWT token authentication with algorithm `none` attack rejection.
  - In-memory thread-safe 6-digit OTP delivery via Gmail SMTP / Resend for password resets.
  - Persistent SQLite conversation history with collapsible sessions and sliding context memory.
- **Modern User Experience**:
  - React 19 + Vite + Tailwind CSS interface.
  - Rich metadata badges (Multi-Hop iterations, Evidence Sufficiency score, Conflict Warning, Table extraction).
  - Collapsible sidebar conversation history, multi-document tag selector, and clean cardless chat interface with full Markdown and LaTeX math rendering (`katex`).

---

## 📂 System Architecture

```
User Query / Document Upload
  │
  ├──► [Document Security Gate] (100 MB limit, MIME validation, path traversal guard)
  │      ▼
  │    [Text & Table Extraction] (PyMuPDF parser + Tabular Grid Extractor)
  │      ▼ (if scanned / low text < 50 chars)
  │    [Tesseract OCR Engine] (300 DPI selective page renderer)
  │      ▼
  │    [Token-Aware Chunking] (500 tokens / 50 overlap with table & page metadata)
  │      ├──► ChromaDB Vector Store (sentence-transformers/all-MiniLM-L6-v2)
  │      └──► BM25 Lexical Inverted Index (in-memory per-user cache)
  │
  └──► [Adaptive Query Processing & Multi-Hop Loop]
         │
         ├── Hop 1: [Dense + Sparse Retrieval] ──► [Hybrid Fusion] ──► [Cross-Encoder Reranker]
         │     ▼
         ├── [Evidence Sufficiency Check] ──► Sufficient? ─(Yes)─► [Generation Stage]
         │     ▼ (No / Multi-Hop Required)
         ├── Hop 2..N: [Sub-Query Generation] ──► [Targeted Retrieval] ──► [Cross-Hop Merge]
         │     ▼
         ├── [Cross-Document Conflict Detection] (Discrepancy & Mismatch Annotation)
         │     ▼
         ├── [Context Expansion & Compression]
         │     ▼
         ├── [Prompt Injection Guard & XML Context Framing]
         │     ▼
         ├── [LLM Generation] (Gemini 3.6 Flash / 2.5 Flash / Local Qwen)
         │     ▼
         ├── [Output Privacy & PII Guard] (API key & sensitive token redaction)
         │     ▼
         Streaming Frontend Markdown / LaTeX Response (with Research Metadata Badges)
```

---

## 🚀 Quick Start

### 1. Prerequisites

- **Python**: 3.10 to 3.14
- **Node.js**: 18+ (with npm)
- **Tesseract OCR** *(Optional for scanned PDF support)*: Standard Windows / Linux installation or placed in system PATH.
- **Ollama** *(Optional for local AI mode)*: Running locally on `http://127.0.0.1:11434`.

### 2. Backend Setup

```bash
# Navigate to repository root
cd NexusAI

# Create and activate virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your configuration (e.g., GEMINI_API_KEY)

# Start backend server (Port 8001)
python -m uvicorn main:app --host 127.0.0.1 --port 8001
```

Backend API will be running at `http://127.0.0.1:8001` (Interactive Swagger Docs: `http://127.0.0.1:8001/docs`).

### 3. Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install Node dependencies
npm install

# Start Vite development server (Port 5173)
npm run dev
```

Frontend application will be available at `http://localhost:5173`.

---

## ⚙️ Environment Configuration

Copy `.env.example` to `.env` and configure the following parameters:

```env
# AI Model Configuration
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.6-flash

# Authentication & Security
NEXUS_AUTH_SECRET_KEY=your_secure_jwt_secret_key
ENVIRONMENT=development
MAX_UPLOAD_SIZE_MB=100

# Email & OTP Configuration
EMAIL_PROVIDER=gmail
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_gmail_app_password
SMTP_FROM_EMAIL=your_email@gmail.com

# Cross-Encoder Reranker & Retrieval
RAG_RERANKER_ENABLED=true
RAG_RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
RAG_RERANKER_CROSS_ENCODER_WEIGHT=0.7
RAG_RERANKER_HYBRID_WEIGHT=0.3
RAG_INITIAL_K=30
RAG_FINAL_K=8

# OCR Configuration
OCR_ENABLED=true
OCR_MIN_TEXT_CHARS_PER_PAGE=50
OCR_DPI=200
OCR_LANGUAGE=eng
TESSERACT_CMD=
```

---

## 🧪 Testing & Validation Suite

Run the comprehensive audit and quality assurance suites:

```bash
# 1. Bytecode Compilation Check
python -m compileall -q .

# 2. Frontend Linter & Production Build Check
cd frontend
npm run lint
npm run build
cd ..

# 3. V1.4 Core Research Test Suites
python -m unittest test_multi_hop_reasoning.py
python -m unittest test_evidence_verification.py
python -m unittest test_table_extraction.py

# 4. Scientific Baseline vs Enhanced Benchmark (30 queries across 7 categories)
python run_scientific_benchmark.py

# 5. Cross-Encoder Regression Suite
python test_cross_encoder_reranker.py

# 6. OCR & Advanced RAG Pipeline Suite
python test_ocr_rag_pipeline.py

# 7. Adaptive RAG Optimizer Suite
python test_rag_optimizer.py

# 8. RAG Grounding & Evaluation Framework Suite
python test_rag_evaluation.py

# 9. Observability, Feedback & Query Cache Suite
python -m unittest test_observability_feedback_cache.py

# 10. Live Security & Comprehensive Audit (Backend server running on 8001)
python security_audit.py
python comprehensive_audit.py
python audit_v1_3_hardening.py
```

---

## 🛡️ License

MIT License — NexusAI Project.

