# NexusAI - Privacy-Aware Advanced RAG Document Intelligence Assistant

NexusAI is an enterprise-grade, privacy-aware **Advanced Retrieval-Augmented Generation (RAG)** platform for document intelligence, semantic search, multi-document reasoning, and question answering supporting documents up to **100 MB**.

---

## 🌟 Key Capabilities & Features

- **Advanced Multi-Stage RAG Pipeline**:
  - **Hybrid Retrieval**: Dual-stream semantic vector retrieval (ChromaDB + Sentence Transformers) and lexical retrieval (tokenized BM25Okapi).
  - **Score Fusion**: Reciprocal Rank Fusion (RRF) and Convex Linear Combination for balanced recall.
  - **True Transformer Cross-Encoder Reranker**: Deep query-document joint attention scoring via `cross-encoder/ms-marco-MiniLM-L-6-v2` executed locally in-process.
  - **Context Expansion & Compression**: Sliding-window context retrieval with redundancy deduplication and token budget optimization.
- **Enterprise Document Processing & OCR**:
  - Native multi-format extraction for PDF, DOCX, and TXT with per-page metadata tracking.
  - **Selective Scanned PDF OCR**: Automatic fallback to Tesseract OCR engine for scanned, image-only, or low-text PDF pages at 300 DPI.
  - 100 MB file upload limit with strict MIME and filename traversal security guards.
- **Multi-Document Reasoning & Citations**:
  - Cross-document synthesis, comparative analysis, and verifiable page-level citation attribution.
- **Privacy & Security Architecture**:
  - **Multi-Tenant User Isolation**: Strict SQL and vector database boundary filtering per `user_id`.
  - **Prompt Injection Defense**: Multi-layer detection and neutralization of jailbreaks, role overriding, and XML boundary escaping.
  - **Output Privacy & PII Guard**: Automated real-time regex sanitization of SSNs, emails, credit cards, and Google API keys.
  - **Right-to-Forget**: Complete cascaded document and vector embedding deletion.
- **Dual AI Providers**:
  - **Cloud LLM**: Google Gemini API (`gemini-2.5-flash` / `gemini-3.6-flash`) with dynamic rate-limit fallbacks.
  - **Local LLM**: In-process / offline Qwen model via Ollama with automatic fallback.
- **Enterprise Authentication & Session Management**:
  - JWT token authentication with algorithm `none` attack rejection.
  - In-memory thread-safe 6-digit OTP delivery via Gmail SMTP / Resend for password resets.
  - Persistent SQLite conversation history with sliding context memory.
- **Modern User Experience**:
  - React 19 + Vite + Tailwind CSS interface.
  - Clean cardless chat interface with full Markdown and LaTeX math rendering (`katex`).

---

## 📂 System Architecture

```
User Query / Document Upload
  │
  ├──► [Document Security Gate] (100 MB limit, MIME validation, path traversal guard)
  │      ▼
  │    [Text Extraction] (PyMuPDF native parser)
  │      ▼ (if scanned / low text < 50 chars)
  │    [Tesseract OCR Engine] (300 DPI selective page renderer)
  │      ▼
  │    [Token-Aware Chunking] (500 tokens / 50 overlap with page metadata)
  │      ├──► ChromaDB Vector Store (sentence-transformers/all-MiniLM-L6-v2)
  │      └──► BM25 Lexical Inverted Index (in-memory per-user cache)
  │
  └──► [Query Processing]
         ├──► Chroma Dense Retrieval (Top-30)
         ├──► BM25 Sparse Retrieval (Top-30)
         ▼
       [Hybrid Score Fusion] (RRF & Convex Combination)
         ▼
       [TRUE Cross-Encoder Reranker] (cross-encoder/ms-marco-MiniLM-L-6-v2)
         ▼
       [Context Expansion & Compression]
         ▼
       [Prompt Injection Guard & XML Context Framing]
         ▼
       [LLM Generation] (Gemini 2.5/3.6 Flash / Local Qwen)
         ▼
       [Output Privacy & PII Guard] (API key & sensitive token redaction)
         ▼
       Streaming Frontend Markdown / LaTeX Response
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
cd NexusAI-GitHub

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
GEMINI_MODEL=gemini-2.5-flash

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

# Cross-Encoder Reranker
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

# 3. Cross-Encoder Regression Suite
python test_cross_encoder_reranker.py

# 4. OCR & Advanced RAG Pipeline Suite
python test_ocr_rag_pipeline.py

# 5. Full 25-Phase Production Audit
python comprehensive_audit.py
```

---

## 🛡️ License

MIT License — NexusAI Project.

