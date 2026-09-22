import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from typing import Optional, List, Dict, Any, Union

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.getenv("CHROMA_DIR")
if not CHROMA_DIR:
    local_chroma = os.path.join(BASE_DIR, "chroma_db")
    alt_chroma = os.path.join(BASE_DIR, "..", "backend", "chroma_db")
    if os.path.isdir(local_chroma) and os.listdir(local_chroma):
        CHROMA_DIR = local_chroma
    elif os.path.isdir(alt_chroma) and os.listdir(alt_chroma):
        CHROMA_DIR = alt_chroma
    else:
        CHROMA_DIR = local_chroma

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 120

print("=" * 70)
print("🔹 Loading HuggingFace embedding model...")
print("Model:", EMBEDDING_MODEL_NAME)
print("=" * 70)

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

embedding_model = HuggingFaceEmbeddings(
    model_name=EMBEDDING_MODEL_NAME,
    model_kwargs={"local_files_only": True},
)

print("✅ Embedding model loaded")


# ============================================================
# CACHED CHROMA VECTOR STORE
# ============================================================

_vector_store: Optional[Chroma] = None


def get_vector_store():
    """
    Return the persistent Chroma vector store.
    The absolute path guarantees that the database is always
    stored beside this Python file, regardless of the process cwd.
    """
    global _vector_store

    if _vector_store is not None:
        return _vector_store

    os.makedirs(CHROMA_DIR, exist_ok=True)

    print("=" * 70)
    print("🔹 Loading Chroma database...")
    print("Directory:", CHROMA_DIR)
    print("=" * 70)

    _vector_store = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embedding_model,
    )

    print("✅ Chroma database loaded and cached")

    try:
        print("📊 Total chunks currently in Chroma:",
              _vector_store._collection.count())
    except Exception as exc:
        print("⚠️ Could not read Chroma count:", str(exc))

    return _vector_store


def create_vector_store(text_or_pages: Union[str, List[Dict[str, Any]], Dict[str, Any]], filename: str, user_id=None, document_id=None):
    """
    Split document text/pages into chunks and add them to Chroma with rich page metadata.
    Supports:
    - Raw text string
    - List of structured page dicts: [{'page_number': 1, 'text': '...', 'extraction_method': 'native'|'ocr'}]
    - Unified extraction dict from extract_document_content: {'text': '...', 'pages': [...], 'extraction_method': '...'}

    Existing chunks belonging to the same filename are removed first,
    so re-uploading a document does not create duplicate chunks.
    """
    if text_or_pages is None:
        raise ValueError("Document content is empty.")

    if not filename:
        raise ValueError("Document filename is required.")

    # Parse inputs into structured chunk items
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=[
            "\n\n",
            "\n",
            ". ",
            "? ",
            "! ",
            " ",
            "",
        ],
    )

    chunks: List[str] = []
    chunk_pages: List[int] = []
    chunk_methods: List[str] = []

    if isinstance(text_or_pages, dict):
        pages_list = text_or_pages.get("pages", [])
        default_method = text_or_pages.get("extraction_method", "native")
        if pages_list:
            for p in pages_list:
                p_num = p.get("page_number", 1)
                p_text = str(p.get("text", "")).strip()
                p_method = p.get("extraction_method", default_method)
                if p_text:
                    p_chunks = splitter.split_text(p_text)
                    for c in p_chunks:
                        if c.strip():
                            chunks.append(c)
                            chunk_pages.append(p_num)
                            chunk_methods.append(p_method)
        else:
            raw_text = str(text_or_pages.get("text", "")).strip()
            if raw_text:
                raw_chunks = splitter.split_text(raw_text)
                for c in raw_chunks:
                    if c.strip():
                        chunks.append(c)
                        chunk_pages.append(1)
                        chunk_methods.append(default_method)

    elif isinstance(text_or_pages, list):
        for p in text_or_pages:
            p_num = p.get("page_number", 1)
            p_text = str(p.get("text", "")).strip()
            p_method = p.get("extraction_method", "native")
            if p_text:
                p_chunks = splitter.split_text(p_text)
                for c in p_chunks:
                    if c.strip():
                        chunks.append(c)
                        chunk_pages.append(p_num)
                        chunk_methods.append(p_method)

    else:
        raw_text = str(text_or_pages).strip()
        if raw_text:
            raw_chunks = splitter.split_text(raw_text)
            for c in raw_chunks:
                if c.strip():
                    chunks.append(c)
                    chunk_pages.append(1)
                    chunk_methods.append("native")

    if not chunks:
        raise ValueError("Document text is empty or no valid chunks were created.")

    print("=" * 70)
    print("📚 VECTOR STORE CREATION")
    print("=" * 70)
    print("Filename:", filename)
    print("User ID:", user_id)
    print("Total Chunks:", len(chunks))
    print("Chunk size:", CHUNK_SIZE)
    print("Chunk overlap:", CHUNK_OVERLAP)

    MAX_INDEX_CHUNKS = 1500
    if len(chunks) > MAX_INDEX_CHUNKS:
        print(f"⚡ Document is exceptionally large ({len(chunks)} chunks). Indexing top {MAX_INDEX_CHUNKS} chunks for high-speed RAG retrieval.")
        chunks = chunks[:MAX_INDEX_CHUNKS]
        chunk_pages = chunk_pages[:MAX_INDEX_CHUNKS]
        chunk_methods = chunk_methods[:MAX_INDEX_CHUNKS]

    vector_store = get_vector_store()

    # Remove old chunks for this filename before replacing them.
    try:
        existing = vector_store._collection.get(
            where={"filename": filename}
        )
        existing_ids = existing.get("ids", []) if existing else []

        if existing_ids:
            vector_store._collection.delete(ids=existing_ids)
            print("🧹 Removed existing chunks:", len(existing_ids))
    except Exception as exc:
        print("⚠️ Existing chunk cleanup skipped:", str(exc))

    metadatas = [
        {
            "filename": filename,
            "source": filename,
            "chunk_index": index,
            "page_number": chunk_pages[index],
            "extraction_method": chunk_methods[index],
            "user_id": str(user_id) if user_id is not None else "",
            "document_id": str(document_id) if document_id is not None else "",
        }
        for index in range(len(chunks))
    ]

    ids = [
        f"{filename}::chunk::{index}"
        for index in range(len(chunks))
    ]

    # Optimized batch insertion with pre-computed embeddings
    batch_size = 64
    total_batches = (len(chunks) + batch_size - 1) // batch_size

    for batch_idx in range(total_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, len(chunks))

        batch_chunks = chunks[start_idx:end_idx]
        batch_metadatas = metadatas[start_idx:end_idx]
        batch_ids = ids[start_idx:end_idx]

        # Generate embeddings in batch
        batch_embeddings = embedding_model.embed_documents(batch_chunks)

        # Direct Chroma upsert with pre-computed embeddings
        vector_store._collection.upsert(
            ids=batch_ids,
            embeddings=batch_embeddings,
            metadatas=batch_metadatas,
            documents=batch_chunks,
        )

    # Invalidate BM25 index cache to ensure freshness
    try:
        from bm25_retriever import invalidate_document_bm25
        invalidate_document_bm25(filename)
    except Exception:
        pass

    print(f"✅ Document '{filename}' indexed successfully ({len(chunks)} chunks in {total_batches} batches)")
    print("Chroma directory:", CHROMA_DIR)

    return vector_store


def delete_document_from_vector_store(filename: str) -> int:
    """
    Remove all Chroma vectors and invalidate BM25 cache for a document.
    Enforces the right-to-forget policy. Returns number of deleted chunks.
    """
    if not filename:
        return 0

    vector_store = get_vector_store()
    deleted_count = 0
    try:
        existing = vector_store._collection.get(
            where={"filename": filename}
        )
        existing_ids = existing.get("ids", []) if existing else []
        if existing_ids:
            vector_store._collection.delete(ids=existing_ids)
            deleted_count = len(existing_ids)
            print(f"🗑️ Deleted vector chunks: {deleted_count} for {filename}")
    except Exception as exc:
        print(f"⚠️ Error removing vectors for {filename}:", str(exc))

    try:
        from bm25_retriever import invalidate_document_bm25
        invalidate_document_bm25(filename)
    except Exception:
        pass

    return deleted_count


def search_documents(query, k=5, filename=None, user_id=None):
    """
    Similarity search across indexed documents.

    If filename is supplied, restrict results to that document.
    """
    if not query or not str(query).strip():
        return []

    vector_store = get_vector_store()

    where_filter = {}
    if filename:
        where_filter["filename"] = filename
    if user_id is not None:
        where_filter["user_id"] = str(user_id)

    search_kwargs = {"k": k}
    if where_filter:
        if len(where_filter) == 1:
            search_kwargs["filter"] = where_filter
        else:
            search_kwargs["filter"] = {"$and": [{k: v} for k, v in where_filter.items()]}

    try:
        return vector_store.similarity_search(
            str(query).strip(),
            **search_kwargs,
        )
    except Exception:
        # Fallback to single filter if complex query fails
        if filename:
            return vector_store.similarity_search(
                str(query).strip(),
                k=k,
                filter={"filename": filename},
            )
        return vector_store.similarity_search(
            str(query).strip(),
            k=k,
        )
