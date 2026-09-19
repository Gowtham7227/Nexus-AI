import re
import math
import threading
from typing import List, Dict, Any, Tuple, Optional


STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't", "have",
    "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers",
    "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm",
    "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself", "let's",
    "me", "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off",
    "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out",
    "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's", "should",
    "shouldn't", "so", "some", "such", "than", "that", "that's", "the", "their",
    "theirs", "them", "themselves", "then", "there", "there's", "these", "they",
    "they'd", "they'll", "they're", "they've", "this", "those", "through", "to", "too",
    "under", "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're",
    "we've", "were", "weren't", "what", "what's", "when", "when's", "where", "where's",
    "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours", "yourself",
    "yourselves"
}


def tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase alphanumeric words without stopwords."""
    if not text:
        return []
    raw_tokens = re.findall(r"[A-Za-z0-9_]+", str(text).lower())
    return [t for t in raw_tokens if t not in STOPWORDS and len(t) >= 2]


class BM25OkapiIndex:
    """
    Lightweight, high-speed pure-Python BM25Okapi index.
    Zero external C/C++ dependencies, deterministic, and highly accurate for lexical retrieval.
    """

    def __init__(self, chunks: Optional[List[Dict[str, Any]]] = None, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = 0
        self.avgdl = 0.0
        self.doc_freqs: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.doc_len: List[int] = []
        self.chunks: List[Dict[str, Any]] = []
        self.doc_token_freqs: List[Dict[str, int]] = []
        if chunks:
            self.build_index(chunks)

    def build_index(self, chunks: List[Dict[str, Any]]) -> None:
        """
        Build BM25 index from a list of chunk dictionaries:
        [{'id': str, 'text': str, 'filename': str, 'chunk_index': int, ...}]
        """
        self.chunks = chunks
        self.corpus_size = len(chunks)
        if self.corpus_size == 0:
            self.avgdl = 0.0
            return

        total_length = 0
        self.doc_len = []
        self.doc_freqs = {}
        self.doc_token_freqs = []

        for chunk in chunks:
            text = chunk.get("text", "")
            tokens = tokenize(text)
            length = len(tokens)
            self.doc_len.append(length)
            total_length += length

            freqs: Dict[str, int] = {}
            for token in tokens:
                freqs[token] = freqs.get(token, 0) + 1
            self.doc_token_freqs.append(freqs)

            for token in freqs.keys():
                self.doc_freqs[token] = self.doc_freqs.get(token, 0) + 1

        self.avgdl = total_length / self.corpus_size if self.corpus_size > 0 else 0.0

        # Calculate smoothed IDF scores
        self.idf = {}
        for token, freq in self.doc_freqs.items():
            # Robertson-Spärck Jones IDF
            idf_val = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0)
            self.idf[token] = max(0.01, idf_val)

    def search(self, query: str, k: int = 10, filename_filter: Optional[List[str]] = None) -> List[Tuple[Dict[str, Any], float]]:
        """
        Score and retrieve top-k chunks matching the query.
        Returns list of tuples: [(chunk_dict, score), ...]
        """
        if self.corpus_size == 0 or not query:
            return []

        q_tokens = tokenize(query)
        if not q_tokens:
            return []

        scores: List[float] = [0.0] * self.corpus_size

        for token in q_tokens:
            if token not in self.idf:
                continue
            token_idf = self.idf[token]

            for i in range(self.corpus_size):
                chunk = self.chunks[i]
                if filename_filter and chunk.get("filename") not in filename_filter:
                    continue

                tf = self.doc_token_freqs[i].get(token, 0)
                if tf == 0:
                    continue

                d_len = self.doc_len[i]
                denom = tf + self.k1 * (1.0 - self.b + self.b * (d_len / (self.avgdl or 1.0)))
                scores[i] += token_idf * (tf * (self.k1 + 1.0)) / (denom or 1.0)

        # Rank documents with positive scores
        scored_results = []
        for i, score in enumerate(scores):
            if score > 0.0:
                chunk = self.chunks[i]
                if filename_filter and chunk.get("filename") not in filename_filter:
                    continue
                scored_results.append((chunk, score))

        scored_results.sort(key=lambda x: x[1], reverse=True)
        return scored_results[:k]


# ============================================================
# BM25 CACHE & RETRIEVAL MANAGER
# ============================================================

_bm25_indices: Dict[str, BM25OkapiIndex] = {}
_bm25_lock = threading.Lock()


def get_or_build_bm25_index(filename: str, chunks: List[Dict[str, Any]]) -> BM25OkapiIndex:
    """Thread-safe index getter / builder for a document."""
    with _bm25_lock:
        if filename in _bm25_indices and len(_bm25_indices[filename].chunks) == len(chunks):
            return _bm25_indices[filename]

        index = BM25OkapiIndex()
        index.build_index(chunks)
        _bm25_indices[filename] = index
        return index


def invalidate_bm25_index(filename: str) -> None:
    """Remove a document from the BM25 index cache (e.g. upon document deletion)."""
    with _bm25_lock:
        _bm25_indices.pop(filename, None)


invalidate_document_bm25 = invalidate_bm25_index
