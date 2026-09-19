import os
import re
from typing import List, Dict, Any

from vector_store import get_vector_store as _get_vector_store
from vector_store import embedding_model


# ============================================================
# CONFIG
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

CHROMA_DIR = os.path.join(
    BASE_DIR,
    "chroma_db"
)

EMBEDDING_MODEL = (
    "sentence-transformers/all-MiniLM-L6-v2"
)

# Normal semantic retrieval
RETRIEVE_K = 20

# Final chunks sent to LLM
FINAL_TOP_K = 6

# Comparison can use more chunks
COMPARISON_TOP_K = 6

# Maximum context sent to LLM
MAX_CONTEXT_CHARS = 14000


# ============================================================
# SHARED EMBEDDING / VECTOR STORE
# ============================================================
#
# IMPORTANT: vector_store.py owns the embedding model and the
# persistent Chroma database. Reuse those same objects here.
# This prevents the embedding model from being loaded a second
# time when the first user question is asked.
#
# Document chunks + embeddings are created by create_vector_store()
# during upload only. Retrieval only searches the already-indexed
# Chroma data.
# ============================================================

_embeddings = embedding_model
_vector_store = None


def get_embeddings():
    return _embeddings


def get_vector_store():

    global _vector_store

    if _vector_store is None:
        print("Loading shared Chroma database...")
        _vector_store = _get_vector_store()
        print("Shared Chroma loaded.")

    return _vector_store


# ============================================================
# FILENAME
# ============================================================

def normalize_filename(
    filename: str
) -> str:

    if not filename:
        return ""

    return os.path.basename(
        str(filename)
    ).strip().lower()


# ============================================================
# SHORT COMPARISON / SIMILARITY DETECTION
# ============================================================

def is_short_comparison_question(
    question: str
) -> bool:
    """
    Detect very short comparison/similarity questions that may
    not contain words such as "compare", "difference", or
    "similarity".

    Examples:
        both same?
        same?
        both similar?
        same or not?
        both same aa?
        rendu documents same aa?
        both same or different?
    """

    q = re.sub(
        r"[^a-z0-9? ]+",
        " ",
        question.lower()
    )

    q = re.sub(
        r"\\s+",
        " ",
        q
    ).strip()

    normalized = q.replace("?", "").strip()

    short_patterns = [
        "both same",
        "both similar",
        "same or not",
        "same or different",
        "both same or different",
        "both similar or not",
        "same aa",
        "same ah",
        "same na",
        "same enti",
        "both same aa",
        "both same ah",
        "both same na",
        "both similar aa",
        "both similar ah",
        "both similar na",
    ]

    if normalized in short_patterns:
        return True

    # Very short standalone questions.
    if normalized in {
        "same",
        "similar",
        "both same",
        "both similar",
        "same aa",
        "same ah",
        "same na",
    }:
        return True

    return False


# ============================================================
# QUESTION TYPE
# ============================================================

def detect_question_type(
    question: str
) -> str:

    q = question.lower().strip()

    # ========================================================
    # COMPARISON
    # ========================================================

    if (
        is_short_comparison_question(q)
        or "compare" in q
        or "comparison" in q
        or "difference" in q
        or "differences" in q
        or "similarity" in q
        or "similarities" in q
        or "similar" in q
        or "both documents" in q
        or "two documents" in q
        or "these documents" in q
        or "these two" in q
        or "versus" in q
        or " vs " in q
        or q.startswith("compare ")
    ):
        return "comparison"


    # ========================================================
    # WHY
    # ========================================================

    if (
        q.startswith("why ")
        or "why did" in q
        or "why was" in q
        or "why were" in q
        or "reason for" in q
        or "reason did" in q
        or "purpose of" in q
        or "purpose for" in q
        or "what was the reason" in q
    ):
        return "why"


    # ========================================================
    # HOW
    # ========================================================

    if (
        q.startswith("how ")
        or "how did" in q
        or "how does" in q
        or "how was" in q
        or "how were" in q
    ):
        return "how"


    # ========================================================
    # SUMMARY / OVERVIEW
    # ========================================================

    if (
        "what is the document about" in q
        or "what's the document about" in q
        or "what is this document about" in q
        or "what is this document" in q
        or "what's this document" in q
        or "what is this file" in q
        or "what's this file" in q
        or "what is this paper about" in q
        or "what is the paper about" in q
        or "tell me about this document" in q
        or "tell me about the document" in q
        or "tell me about this file" in q
        or "describe this document" in q
        or "describe the document" in q
        or "explain the document" in q
        or "explain this document" in q
        or "explain about the document" in q
        or "explain about this document" in q
        or "explain about document" in q
        or "explain document" in q
        or "explain this" in q
        or "explain file" in q
        or "about the document" in q
        or "about this document" in q
        or "document overview" in q
        or "overview of the document" in q
        or "main purpose of the document" in q
        or "main purpose of this document" in q
        or q == "about"
        or "summarize" in q
        or "summary" in q
    ):
        return "overview"


    # ========================================================
    # DEFINITION
    # ========================================================

    if (
        q.startswith("what is ")
        or q.startswith("what are ")
        or q.startswith("what does ")
        or "define " in q
        or "meaning of " in q
    ):
        return "definition"


    return "general"


# ============================================================
# KEYWORDS
# ============================================================

def extract_keywords(
    question: str
) -> List[str]:

    words = re.findall(
        r"[A-Za-z0-9][A-Za-z0-9_.-]*",
        question.lower()
    )

    stop_words = {
        "what",
        "is",
        "are",
        "the",
        "a",
        "an",
        "of",
        "to",
        "for",
        "in",
        "on",
        "with",
        "and",
        "or",
        "did",
        "do",
        "does",
        "they",
        "them",
        "their",
        "it",
        "this",
        "that",
        "was",
        "were",
        "why",
        "how",
        "can",
        "could",
        "would",
        "should",
        "about",
        "document",
        "documents",
        "please",
        "tell",
        "me",
        "give",
        "point",
        "points",
        "main",
        "key",
        "important",
        "please",
        "explain",
        "used",
        "use",
        "using",
        "these",
        "two",
        "both",
        "compare",
        "comparison",
        "difference",
        "differences",
        "similarity",
        "similarities",
    }

    result = []

    for word in words:

        if word in stop_words:
            continue

        if len(word) < 2:
            continue

        if word not in result:
            result.append(word)

    return result


# ============================================================
# QUERY EXPANSION
# ============================================================

def build_queries(
    question: str
) -> List[str]:

    q = question.strip()

    qtype = detect_question_type(
        q
    )

    keywords = extract_keywords(
        q
    )

    keyword_text = " ".join(
        keywords
    )

    queries = [
        q
    ]


    # ========================================================
    # COMPARISON
    # ========================================================

    if qtype == "comparison":

        queries.extend([

            # General comparison evidence
            "document main topic",
            "document main subject",
            "document purpose",
            "document objective",

            # Similarity / same-topic evidence
            "what both documents have in common",
            "similarities between the documents",
            "common points in both documents",
            "are the documents similar",
            "same topic same subject common findings",


            "document purpose",

            "document objective",

            "research objective",

            "main subject",

            "key findings",

            "important findings",

            "methodology",

            "approach",

            "results",

            "conclusion",

            "key concepts",

            "important points",

            "summary",

            "overview"

        ])


    # ========================================================
    # WHY
    # ========================================================

    elif qtype == "why":

        queries.extend([

            f"{keyword_text} reason",

            f"{keyword_text} purpose",

            f"{keyword_text} motivation",

            f"{keyword_text} why chosen",

            f"{keyword_text} why used",

            f"{keyword_text} objective",

            f"{keyword_text} benefits",

            f"{keyword_text} findings",

            f"{keyword_text} results",

            f"{keyword_text} accuracy",

            f"{keyword_text} effectiveness"

        ])


        # RAG-specific expansion

        if "rag" in keywords:

            queries.extend([

                "RAG reason for using RAG",

                "RAG motivation",

                "RAG purpose",

                "why use RAG",

                "RAG highest accuracy",

                "RAG prompt engineering accuracy",

                "OpenAI findings RAG",

                "RAG effective technique",

                "RAG document processing reason",

                "RAG results accuracy",

                "RAG chosen because",

                "reason for choosing RAG"

            ])


    # ========================================================
    # HOW
    # ========================================================

    elif qtype == "how":

        queries.extend([

            f"{keyword_text} process",

            f"{keyword_text} workflow",

            f"{keyword_text} implementation",

            f"{keyword_text} methodology",

            f"{keyword_text} steps",

            f"{keyword_text} architecture"

        ])


    # ========================================================
    # OVERVIEW
    # ========================================================

    elif qtype == "overview":

        queries.extend([

            "document main topic",

            "document purpose",

            "document objective",

            "research objective",

            "main subject",

            "main findings",

            "methodology",

            "results",

            "key concepts",

            "important points",

            "conclusion"

        ])


    # ========================================================
    # DEFINITION
    # ========================================================

    elif qtype == "definition":

        queries.extend([

            f"{keyword_text} definition",

            f"{keyword_text} meaning",

            f"{keyword_text} description",

            f"{keyword_text} explained"

        ])


    # ========================================================
    # GENERAL
    # ========================================================

    else:

        queries.extend([

            f"{keyword_text} information",

            f"{keyword_text} details",

            f"{keyword_text} explanation",

            f"{keyword_text} findings"

        ])


    # ========================================================
    # REMOVE DUPLICATES
    # ========================================================

    final_queries = []

    seen = set()

    for query in queries:

        query = query.strip()

        if not query:
            continue

        key = re.sub(
            r"\s+",
            " ",
            query.lower()
        )

        if key in seen:
            continue

        seen.add(key)

        final_queries.append(
            query
        )

    return final_queries


# ============================================================
# FILENAME MATCH
# ============================================================

def filename_matches(
    metadata: Dict[str, Any],
    filename: str
) -> bool:

    if not filename:
        return True

    target = normalize_filename(
        filename
    )

    current = normalize_filename(
        metadata.get(
            "filename",
            ""
        )
    )

    return current == target


# ============================================================
# KEYWORD SCORE
# ============================================================

def keyword_score(
    text: str,
    question: str
) -> float:

    if not text:
        return 0.0

    text_lower = text.lower()

    keywords = extract_keywords(
        question
    )

    score = 0.0

    for keyword in keywords:

        if keyword in text_lower:

            score += 2.0


    qtype = detect_question_type(
        question
    )


    # ========================================================
    # WHY EVIDENCE
    # ========================================================

    if qtype == "why":

        evidence_terms = [

            "because",
            "reason",
            "purpose",
            "motivation",
            "why",
            "finding",
            "findings",
            "result",
            "results",
            "achieved",
            "effective",
            "effectiveness",
            "accuracy",
            "benefit",
            "advantage",
            "objective",
            "chosen",
            "used"

        ]

        for term in evidence_terms:

            if term in text_lower:

                score += 2.5


    # ========================================================
    # OVERVIEW EVIDENCE
    # ========================================================

    if qtype in (
        "overview",
        "comparison"
    ):

        overview_terms = [

            "abstract",
            "introduction",
            "overview",
            "objective",
            "purpose",
            "aim",
            "methodology",
            "method",
            "approach",
            "results",
            "findings",
            "conclusion",
            "summary",
            "key finding",
            "research",
            "study"

        ]

        for term in overview_terms:

            if term in text_lower:

                score += 3.0


    # ========================================================
    # RAG EVIDENCE
    # ========================================================

    if "rag" in keywords:

        rag_terms = [

            "rag",
            "retrieval-augmented generation",
            "retrieval augmented generation",
            "prompt engineering",
            "openai",
            "highest accuracy",
            "most effective",
            "document processing",
            "gpt-3.5",
            "langchain",
            "faiss"

        ]

        for term in rag_terms:

            if term in text_lower:

                score += 4.0


    return score


# ============================================================
# DIRECT DOCUMENT CHUNKS
# ============================================================

def get_all_document_chunks(
    vector_store,
    filename: str
):

    """
    Get ALL chunks belonging to the selected document.

    This is important for comparison questions.

    We do NOT depend on global semantic top-K here because
    a generic query such as "compare two documents" may not
    retrieve chunks from every document.
    """

    try:

        data = vector_store.get(
            include=[
                "documents",
                "metadatas"
            ]
        )

    except Exception as e:

        print(
            "Direct document retrieval failed:",
            e
        )

        return []


    documents = data.get(
        "documents",
        []
    )

    metadatas = data.get(
        "metadatas",
        []
    )


    target = normalize_filename(
        filename
    )

    results = []


    for text, metadata in zip(
        documents,
        metadatas
    ):

        metadata = (
            metadata
            if metadata
            else {}
        )

        current = normalize_filename(
            metadata.get(
                "filename",
                ""
            )
        )

        if current != target:
            continue

        if not text:
            continue

        text = text.strip()

        if not text:
            continue

        results.append({

            "text": text,

            "metadata": metadata,

            "distance": 0.0,

            "semantic": 1.0,

            "lexical": 0.0,

            "score": 0.0,

            "query": "DIRECT_DOCUMENT_RETRIEVAL"

        })


    return results


# ============================================================
# COMPARISON RETRIEVAL
# ============================================================

def retrieve_comparison_context(
    question: str,
    filename: str,
    top_k: int
):

    """
    Special retrieval path for comparison questions.

    Instead of asking Chroma for global top-K results,
    first collect chunks ONLY from the selected document.

    Then rank those chunks according to how useful they are
    for comparing documents.
    """

    print(
        "\n🔥 COMPARISON RETRIEVAL MODE"
    )

    print(
        "Document:",
        repr(filename)
    )


    try:

        vector_store = get_vector_store()

    except Exception as e:

        print(
            "Vector store error:",
            e
        )

        return ""


    # --------------------------------------------------------
    # Get all chunks belonging to this document
    # --------------------------------------------------------

    candidates = get_all_document_chunks(
        vector_store,
        filename
    )


    print(
        "Direct chunks found:",
        len(candidates)
    )


    if not candidates:

        print(
            "❌ No chunks found for comparison document:",
            filename
        )

        return ""


    # --------------------------------------------------------
    # Score chunks
    # --------------------------------------------------------

    for item in candidates:

        text = item["text"]

        score = keyword_score(
            text,
            question
        )

        text_lower = text.lower()


        # Strong boost for useful document-level information

        important_terms = [

            "abstract",
            "introduction",
            "objective",
            "purpose",
            "aim",
            "method",
            "methodology",
            "approach",
            "dataset",
            "results",
            "findings",
            "conclusion",
            "discussion",
            "summary",
            "overview"

        ]

        for term in important_terms:

            if term in text_lower:

                score += 4.0


        # Prefer chunks with meaningful amount of text

        text_length = len(text)

        if text_length >= 300:

            score += 2.0

        if text_length >= 600:

            score += 2.0


        item["score"] = score


    # --------------------------------------------------------
    # Sort
    # --------------------------------------------------------

    candidates.sort(
        key=lambda x: x["score"],
        reverse=True
    )


    # --------------------------------------------------------
    # Select
    # --------------------------------------------------------

    selected = candidates[
        :top_k
    ]


    print(
        "Selected comparison chunks:",
        len(selected)
    )


    for i, item in enumerate(
        selected,
        1
    ):

        print(
            f"\n--- COMPARISON CHUNK {i} ---"
        )

        print(
            "Score:",
            round(
                item["score"],
                3
            )
        )

        print(
            "Metadata:",
            item["metadata"]
        )

        print(
            item["text"][:1200]
        )


    # --------------------------------------------------------
    # Build context
    # --------------------------------------------------------

    context_parts = []

    current_length = 0


    for i, item in enumerate(
        selected,
        1
    ):

        block = (

            f"[DOCUMENT: {filename}]\n"

            f"[DOCUMENT CHUNK {i}]\n"

            f"{item['text']}\n"

            f"[/DOCUMENT CHUNK {i}]\n"

            f"[/DOCUMENT: {filename}]"

        )


        if (
            current_length
            + len(block)
            + 2
            >
            MAX_CONTEXT_CHARS
        ):

            break


        context_parts.append(
            block
        )

        current_length += (
            len(block)
            + 2
        )


    context = "\n\n".join(
        context_parts
    )


    print(
        "\nComparison context length:",
        len(context)
    )


    return context


# ============================================================
# NORMAL RETRIEVAL
# ============================================================

def retrieve_context(
    question: str,
    filename: str = None,
    top_k: int = FINAL_TOP_K
):

    if not question:

        return ""


    print(
        "=" * 70
    )

    print(
        "RETRIEVER DEBUG"
    )

    print(
        "=" * 70
    )

    print(
        "Original Question:",
        repr(question)
    )

    print(
        "Filename:",
        repr(filename)
    )


    qtype = detect_question_type(
        question
    )


    print(
        "Question Type:",
        qtype
    )


    # ========================================================
    # COMPARISON MODE
    # ========================================================

    if qtype == "comparison":

        return retrieve_comparison_context(
            question,
            filename,
            COMPARISON_TOP_K
        )


    # ========================================================
    # FAST FACTUAL MODE
    # ========================================================
    #
    # Short factual questions such as:
    #   "How many regions does the Sun have?"
    # do not need the full query-expansion pipeline.
    #
    # The previous flow generated multiple semantic variants
    # (process/workflow/implementation/etc.) even for a simple
    # factual question. That adds unnecessary embedding work.
    #
    # Keep the original question as the single retrieval query.
    # Complex/comparison/overview questions continue normally.
    # ========================================================

    normalized_question = question.lower().strip()

    if (
        qtype == "how"
        and (
            normalized_question.startswith("how many ")
            or normalized_question.startswith("how much ")
        )
        and len(normalized_question.split()) <= 12
    ):
        queries = [question]

        print(
            "\n⚡ FAST FACTUAL RETRIEVAL MODE"
        )

        print(
            "Using 1 retrieval query instead of expanded queries."
        )

    else:

        # ========================================================
        # NORMAL QUERY EXPANSION
        # ========================================================

        queries = build_queries(
            question
        )


    print(
        "\nRetrieval Queries:"
    )


    for i, query in enumerate(
        queries,
        1
    ):

        print(
            f"{i}. {query}"
        )


    # ========================================================
    # VECTOR STORE
    # ========================================================

    try:

        vector_store = get_vector_store()

    except Exception as e:

        print(
            "Vector store error:",
            e
        )

        return ""


    # ========================================================
    # COLLECT MANY CANDIDATES
    # ========================================================

    candidates = []


    for query in queries:

        try:

            results = (

                vector_store
                .similarity_search_with_score(
                    query,
                    k=RETRIEVE_K
                )

            )

        except Exception as e:

            print(
                "Query failed:",
                query,
                e
            )

            continue


        for document, distance in results:

            metadata = (

                document.metadata

                if document.metadata

                else {}

            )


            # ------------------------------------------------
            # SAME DOCUMENT ONLY
            # ------------------------------------------------

            if not filename_matches(
                metadata,
                filename
            ):

                continue


            text = (

                document.page_content

                or ""

            ).strip()


            if not text:

                continue


            # ------------------------------------------------
            # Semantic score
            # ------------------------------------------------

            semantic = 1.0 / (

                1.0
                + float(distance)

            )


            # ------------------------------------------------
            # Keyword score
            # ------------------------------------------------

            lexical = keyword_score(
                text,
                question
            )


            # ------------------------------------------------
            # Combined score
            # ------------------------------------------------

            score = (

                semantic * 10.0

                + lexical

            )


            candidates.append({

                "text": text,

                "metadata": metadata,

                "distance": float(
                    distance
                ),

                "semantic": semantic,

                "lexical": lexical,

                "score": score,

                "query": query

            })


    # ========================================================
    # HYBRID LEXICAL DOCUMENT BOOST
    # ========================================================
    # Semantic search can miss a chunk when the user's wording is
    # different from the wording used in the document. For example:
    #
    #   "What happened in India?"
    #   "What are the main points about India?"
    #
    # Both should retrieve chunks containing "India".
    #
    # When a specific document is selected, inspect its chunks
    # lexically as a second retrieval signal and merge the strongest
    # matches with the semantic candidates.

    if filename:

        direct_chunks = get_all_document_chunks(
            vector_store,
            filename
        )

        print(
            "\n📚 Direct document chunks available:",
            len(direct_chunks)
        )

        question_keywords = extract_keywords(question)

        # Only use the lexical pass when the question contains
        # meaningful topic/entity words.
        if question_keywords and direct_chunks:

            lexical_candidates = []

            for item in direct_chunks:

                lexical = keyword_score(
                    item["text"],
                    question
                )

                if lexical > 0:

                    # Strong enough to compete with semantic results.
                    item["lexical"] = lexical
                    item["score"] = (
                        12.0
                        + lexical * 2.0
                    )
                    item["query"] = (
                        "DIRECT_LEXICAL_RETRIEVAL"
                    )

                    lexical_candidates.append(item)

            lexical_candidates.sort(
                key=lambda x: x["score"],
                reverse=True
            )

            # Merge lexical matches into semantic candidates.
            candidates.extend(
                lexical_candidates[:RETRIEVE_K]
            )

            print(
                "🔎 Direct lexical matches:",
                len(lexical_candidates)
            )

        # If semantic + lexical retrieval still found nothing,
        # fall back to the selected document.
        if not candidates:

            print(
                "\n⚠️ No semantic or lexical candidates found."
            )

            print(
                "🔄 Using selected document fallback..."
            )

            for item in direct_chunks:

                lexical = keyword_score(
                    item["text"],
                    question
                )

                item["lexical"] = lexical
                item["score"] = (
                    10.0 + lexical
                )
                item["query"] = (
                    "DIRECT_DOCUMENT_FALLBACK"
                )

                candidates.append(item)

            print(
                "📄 Fallback candidates:",
                len(candidates)
            )


    # ========================================================
    # DEDUPLICATE
    # ========================================================

    unique = {}


    for item in candidates:

        key = (

            normalize_filename(

                item["metadata"].get(
                    "filename",
                    ""
                )

            ),

            item["text"]

        )


        if key not in unique:

            unique[key] = item

        else:

            if (

                item["score"]

                >

                unique[key]["score"]

            ):

                unique[key] = item


    candidates = list(
        unique.values()
    )


    # ========================================================
    # SPECIAL EVIDENCE BOOST
    # ========================================================

    question_lower = (
        question.lower()
    )


    for item in candidates:

        text_lower = (
            item["text"].lower()
        )


        # ----------------------------------------------------
        # WHY QUESTIONS
        # ----------------------------------------------------

        if qtype == "why":

            evidence_phrases = [

                "because",

                "reason",

                "purpose",

                "motivation",

                "achieved the highest",

                "highest accuracy",

                "most effective",

                "findings revealed",

                "openai's findings",

                "study examines",

                "used because",

                "chosen because",

                "effective technique"

            ]


            for phrase in evidence_phrases:

                if phrase in text_lower:

                    item["score"] += 20.0


        # ----------------------------------------------------
        # RAG-SPECIFIC EVIDENCE
        # ----------------------------------------------------

        if "rag" in question_lower:

            rag_evidence = [

                "rag",

                "prompt engineering",

                "highest accuracy",

                "openai",

                "most effective",

                "document processing",

                "gpt-3.5",

                "langchain",

                "faiss"

            ]


            for phrase in rag_evidence:

                if phrase in text_lower:

                    item["score"] += 15.0


        # ----------------------------------------------------
        # DIRECT TOPIC / ENTITY MATCH
        # ----------------------------------------------------
        # Exact topic words from the user's question are valuable
        # evidence even when the semantic wording differs.

        direct_keywords = extract_keywords(question)

        if direct_keywords:

            direct_hits = sum(
                1
                for keyword in direct_keywords
                if keyword in text_lower
            )

            if direct_hits > 0:
                item["score"] += (
                    direct_hits * 5.0
                )


    # ========================================================
    # SORT
    # ========================================================

    candidates.sort(

        key=lambda x:
            x["score"],

        reverse=True

    )


    print(
        "\nTotal unique candidates:",
        len(candidates)
    )


    # ========================================================
    # SELECT FINAL CHUNKS
    # ========================================================

    selected = candidates[
        :top_k
    ]


    print(
        "\nSelected chunks:"
    )


    for i, item in enumerate(
        selected,
        1
    ):

        print(
            f"\n--- CHUNK {i} ---"
        )

        print(
            "Score:",
            round(
                item["score"],
                3
            )
        )

        print(
            "Semantic:",
            round(
                item["semantic"],
                3
            )
        )

        print(
            "Lexical:",
            round(
                item["lexical"],
                3
            )
        )

        print(
            "Query:",
            item["query"]
        )

        print(
            "Metadata:",
            item["metadata"]
        )

        print(
            item["text"][:1500]
        )


    # ========================================================
    # BUILD CONTEXT
    # ========================================================
    #
    # Short factual count questions normally need only the
    # strongest evidence chunk. Keeping the context tiny reduces
    # request size and avoids making Gemini process unrelated
    # chunks. All other question types keep the existing context.
    # ========================================================

    fast_factual_question = (
        qtype == "how"
        and (
            normalized_question.startswith("how many ")
            or normalized_question.startswith("how much ")
        )
        and len(normalized_question.split()) <= 12
    )

    if fast_factual_question and selected:
        # Keep the normal top-K evidence for factual questions.
        # The exact answer may be in a lower-ranked chunk when generic
        # keyword matches create score ties. The earlier 6-chunk flow
        # successfully answered this type of question, so do not collapse
        # the evidence to one chunk.
        print(
            "\n⚡ FAST FACTUAL CONTEXT MODE"
        )
        print(
            f"Using {len(selected)} ranked evidence chunks for Gemini."
        )

    context_parts = []

    current_length = 0


    for i, item in enumerate(
        selected,
        1
    ):

        block = (

            f"[DOCUMENT CHUNK {i}]\n"

            f"{item['text']}\n"

            f"[/DOCUMENT CHUNK {i}]"

        )


        if (

            current_length
            + len(block)
            + 2

            >

            MAX_CONTEXT_CHARS

        ):

            break


        context_parts.append(
            block
        )


        current_length += (

            len(block)
            + 2

        )


    context = "\n\n".join(
        context_parts
    )


    print(
        "\nFiltered chunks:",
        len(selected)
    )


    print(
        "Final Context Length:",
        len(context)
    )


    print(
        "=" * 70
    )


    return context


# ============================================================
# COMPATIBILITY ALIASES
# ============================================================

def get_relevant_context(
    question: str,
    filename: str = None,
    top_k: int = FINAL_TOP_K
):

    return retrieve_context(
        question,
        filename,
        top_k
    )


def search_document(
    question: str,
    filename: str = None,
    top_k: int = FINAL_TOP_K
):

    return retrieve_context(
        question,
        filename,
        top_k
    )