import os

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings


# ============================================================
# CONFIGURATION
# ============================================================

CHROMA_DIR = "chroma_db"

EMBEDDING_MODEL_NAME = (
    "sentence-transformers/all-MiniLM-L6-v2"
)

CHUNK_SIZE = 800
CHUNK_OVERLAP = 120


# ============================================================
# EMBEDDING MODEL
# ============================================================

print("=" * 70)
print("🔹 Loading HuggingFace embedding model...")
print("Model:", EMBEDDING_MODEL_NAME)
print("=" * 70)

embedding_model = HuggingFaceEmbeddings(
    model_name=EMBEDDING_MODEL_NAME
)

print("✅ Embedding model loaded")


# ============================================================
# CACHED CHROMA VECTOR STORE
# ============================================================

_vector_store = None


# ============================================================
# GET VECTOR STORE
# ============================================================

def get_vector_store():
    """
    Load the existing Chroma vector database once and reuse
    the same Chroma object for all subsequent operations.

    The database remains persistent on disk. This cache avoids
    repeatedly creating a new Chroma wrapper for every question.
    """

    global _vector_store

    if _vector_store is not None:
        print("⚡ Using cached Chroma database")
        return _vector_store

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
        count = _vector_store._collection.count()

        print(
            "📊 Total chunks currently in Chroma:",
            count,
        )

    except Exception as e:
        print(
            "⚠️ Could not read Chroma count:",
            str(e),
        )

    return _vector_store


# ============================================================
# CREATE / UPDATE VECTOR STORE
# ============================================================

def create_vector_store(text, filename):

    print("\n")
    print("=" * 70)
    print("📚 VECTOR STORE CREATION")
    print("=" * 70)

    print("Filename:", filename)

    # --------------------------------------------------------
    # Validate input
    # --------------------------------------------------------

    if text is None:

        print("❌ Text is None")

        return None

    text = str(text).strip()

    print("Extracted text length:", len(text))

    if not text:

        print("❌ No text available for indexing")

        return None

    # --------------------------------------------------------
    # Create chunks
    # --------------------------------------------------------

    print("-" * 70)
    print("✂️ Creating document chunks...")
    print(
        "Chunk size:",
        CHUNK_SIZE,
    )

    print(
        "Chunk overlap:",
        CHUNK_OVERLAP,
    )

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

    chunks = splitter.split_text(text)

    print(
        "📦 Number of chunks created:",
        len(chunks),
    )

    if not chunks:

        print("❌ No chunks were created")

        return None

    # --------------------------------------------------------
    # Remove empty chunks
    # --------------------------------------------------------

    chunks = [
        chunk.strip()
        for chunk in chunks
        if chunk and chunk.strip()
    ]

    print(
        "📦 Valid chunks after cleanup:",
        len(chunks),
    )

    if not chunks:

        print("❌ All chunks were empty")

        return None

    # --------------------------------------------------------
    # Load Chroma
    # --------------------------------------------------------

    try:

        vector_db = get_vector_store()

        print("✅ Chroma database ready for indexing")

    except Exception as e:

        print(
            "❌ Failed to open Chroma:",
            str(e),
        )

        raise

    # --------------------------------------------------------
    # Remove previous chunks for same document
    # --------------------------------------------------------

    print("-" * 70)
    print("🔎 Checking existing chunks for:", filename)

    try:

        existing = vector_db._collection.get(
            where={
                "filename": filename
            }
        )

        existing_ids = existing.get(
            "ids",
            []
        )

        if existing_ids:

            print(
                "🗑️ Existing chunks found:",
                len(existing_ids),
            )

            vector_db._collection.delete(
                ids=existing_ids
            )

            print(
                "✅ Old chunks removed"
            )

        else:

            print(
                "ℹ️ No previous chunks found"
            )

    except Exception as e:

        print(
            "⚠️ Existing chunk cleanup failed:",
            str(e),
        )

        # Do not stop indexing.
        # We can still add the new document.

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    metadatas = []

    for index in range(len(chunks)):

        metadatas.append(
            {
                "filename": filename,
                "chunk_index": index,
                "total_chunks": len(chunks),
            }
        )

    # --------------------------------------------------------
    # Deterministic IDs
    # --------------------------------------------------------

    safe_filename = (
        os.path.basename(filename)
        .replace(" ", "_")
    )

    ids = []

    for index in range(len(chunks)):

        ids.append(
            f"{safe_filename}__chunk_{index}"
        )

    # --------------------------------------------------------
    # Add chunks
    # --------------------------------------------------------

    print("-" * 70)
    print("🧠 Creating embeddings and storing chunks...")

    try:

        vector_db.add_texts(
            texts=chunks,
            metadatas=metadatas,
            ids=ids,
        )

        print(
            "✅ Chunks successfully added to ChromaDB"
        )

    except Exception as e:

        print(
            "❌ Failed to add chunks to ChromaDB:",
            str(e),
        )

        raise

    # --------------------------------------------------------
    # Verify document was actually stored
    # --------------------------------------------------------

    try:

        verification = (
            vector_db._collection.get(
                where={
                    "filename": filename
                },
                include=[
                    "metadatas"
                ],
            )
        )

        stored_ids = verification.get(
            "ids",
            []
        )

        print("-" * 70)
        print(
            "🔍 INDEX VERIFICATION"
        )

        print(
            "Filename:",
            filename,
        )

        print(
            "Expected chunks:",
            len(chunks),
        )

        print(
            "Stored chunks:",
            len(stored_ids),
        )

        if len(stored_ids) == len(chunks):

            print(
                "✅ DOCUMENT INDEXED SUCCESSFULLY"
            )

        else:

            print(
                "⚠️ Stored chunk count does not match expected count"
            )

    except Exception as e:

        print(
            "⚠️ Verification failed:",
            str(e),
        )

    # --------------------------------------------------------
    # Total Chroma count
    # --------------------------------------------------------

    try:

        total_count = (
            vector_db._collection.count()
        )

        print("-" * 70)

        print(
            "📊 Total chunks in Chroma:",
            total_count,
        )

    except Exception as e:

        print(
            "⚠️ Could not read total count:",
            str(e),
        )

    print("=" * 70)
    print(
        "🎉 VECTOR STORE CREATION COMPLETE"
    )
    print("=" * 70)
    print("\n")

    return vector_db