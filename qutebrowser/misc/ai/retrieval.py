# SPDX-FileCopyrightText: Camilo <camilo@example.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Retrieve candidate commands given a natural language query.

Three backends (tried in order):
  1. sentence-transformers (all-MiniLM-L6-v2) – highest quality.
  2. scikit-learn TfidfVectorizer – good lexical matching.
  3. Pure-stdlib TF-IDF fallback – zero extra dependencies.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter

from qutebrowser.misc.ai.types import CandidateCommand

logger = logging.getLogger('ai')

# ---------------------------------------------------------------------------
#  Embedding-based path (sentence-transformers)
# ---------------------------------------------------------------------------

_EMBEDDER = None


def _get_embedder():
    """Lazy-load the sentence-transformers model."""
    global _EMBEDDER  # noqa: PLW0603
    if _EMBEDDER is not None:
        return _EMBEDDER
    try:
        from sentence_transformers import SentenceTransformer
        _EMBEDDER = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("Loaded sentence-transformers model")
    except Exception as exc:
        _EMBEDDER = False
        logger.info("sentence-transformers unavailable, using fallback: %s", exc)
    return _EMBEDDER


def _retrieve_embeddings(
    query: str,
    corpus: list[CandidateCommand],
) -> list[float]:
    """Score corpus entries via sentence-transformers cosine similarity."""
    embedder = _get_embedder()
    if not embedder:
        return []

    texts = [_text_for_entry(e) for e in corpus]
    all_texts = texts + [query]
    embeddings = embedder.encode(all_texts)
    query_emb = embeddings[-1]
    scores = []
    for doc_emb in embeddings[:-1]:
        sim = _cosine_sim(doc_emb, query_emb)
        scores.append(float(sim))
    return scores


def _cosine_sim(a, b):
    dot = sum(ai * bi for ai, bi in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ---------------------------------------------------------------------------
#  scikit-learn TF-IDF path
# ---------------------------------------------------------------------------

_HAS_SKLEARN = None


def _check_sklearn() -> bool:
    """Check whether scikit-learn is available (lazy, once)."""
    global _HAS_SKLEARN  # noqa: PLW0603
    if _HAS_SKLEARN is not None:
        return _HAS_SKLEARN
    try:
        import sklearn.feature_extraction.text  # noqa: F401
        _HAS_SKLEARN = True
        logger.info("scikit-learn available for TF-IDF retrieval")
    except ImportError:
        _HAS_SKLEARN = False
        logger.info("scikit-learn not available, using stdlib TF-IDF fallback")
    return _HAS_SKLEARN


def _retrieve_tfidf_sklearn(
    query: str,
    corpus: list[CandidateCommand],
) -> list[float]:
    """Score corpus entries via sklearn's TfidfVectorizer."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    corpus_texts = [_text_for_entry(e) for e in corpus]
    vectorizer = TfidfVectorizer(
        analyzer='char_wb',
        ngram_range=(3, 6),
        lowercase=True,
    )
    tfidf_matrix = vectorizer.fit_transform(corpus_texts)
    query_vec = vectorizer.transform([query])
    sims = cosine_similarity(query_vec, tfidf_matrix).flatten()
    return [float(s) for s in sims]


# ---------------------------------------------------------------------------
#  Pure-stdlib TF-IDF fallback path
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    """Lower-case tokenisation, keeping only word characters."""
    return re.findall(r'\w+', text.lower())


def _retrieve_tfidf_stdlib(
    query: str,
    corpus: list[CandidateCommand],
) -> list[float]:
    """Score corpus entries via a hand-rolled TF-IDF + cosine similarity.

    Zero extra dependencies – uses only ``math``, ``re``, and
    ``collections.Counter``.
    """
    corpus_texts = [_text_for_entry(e) for e in corpus]
    query_text = query

    vocab: dict[str, int] = {}
    for text in corpus_texts + [query_text]:
        for token in _tokenize(text):
            if token not in vocab:
                vocab[token] = len(vocab)

    n_docs = len(corpus_texts)
    if n_docs == 0 or not vocab:
        return [0.0] * n_docs

    doc_freq: Counter[str] = Counter()
    for text in corpus_texts:
        seen = set(_tokenize(text))
        for token in seen:
            if token in vocab:
                doc_freq[token] += 1

    def _vectorize(text: str) -> list[float]:
        vec = [0.0] * len(vocab)
        tokens = _tokenize(text)
        tf = Counter(tokens)
        for token, count in tf.items():
            if token in vocab:
                idx = vocab[token]
                tf_val = 1.0 + math.log10(count) if count > 0 else 0.0
                idf_val = math.log10((n_docs + 1) / (doc_freq[token] + 1)) + 1.0
                vec[idx] = tf_val * idf_val
        return vec

    def _sim(a: list[float], b: list[float]) -> float:
        dot = sum(ai * bi for ai, bi in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    query_vec = _vectorize(query_text)
    scores = []
    for text in corpus_texts:
        scores.append(_sim(query_vec, _vectorize(text)))
    return scores


# ---------------------------------------------------------------------------
#  Public API
# ---------------------------------------------------------------------------


def _text_for_entry(entry: CandidateCommand) -> str:
    """Build a searchable text blob for a command entry."""
    parts = [entry.name.replace('-', ' '), entry.description]
    for arg in entry.args:
        parts.append(arg.get('name', ''))
    return ' '.join(parts)


def _retrieve_tfidf(
    query: str,
    corpus: list[CandidateCommand],
) -> list[float]:
    """Score corpus entries via TF-IDF.

    Tries scikit-learn first; falls back to pure-stdlib implementation.
    """
    if _check_sklearn():
        return _retrieve_tfidf_sklearn(query, corpus)
    return _retrieve_tfidf_stdlib(query, corpus)


def retrieve(
    query: str,
    corpus: list[CandidateCommand],
    k: int = 8,
) -> list[CandidateCommand]:
    """Return the top-*k* candidate commands ranked by relevance to *query*.

    Tries the sentence-transformers embedder first; falls back to TF-IDF
    (via scikit-learn if available, otherwise pure-stdlib).
    """
    if not corpus:
        return []

    scores = _retrieve_embeddings(query, corpus)
    if not scores:
        scores = _retrieve_tfidf(query, corpus)

    indexed: list[tuple[float, int, CandidateCommand]] = []
    for i, entry in enumerate(corpus):
        indexed.append((scores[i], i, entry))

    indexed.sort(key=lambda x: (-x[0], x[1]))
    return [entry for _, _, entry in indexed[:k]]
