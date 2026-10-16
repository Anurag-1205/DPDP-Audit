"""Keyword search over the paragraphs of one privacy policy (TF-IDF)."""
from __future__ import annotations

import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel


def split_paragraphs(policy_text: str) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", policy_text)]
    return [p for p in paras if p]


def search_policy(policy_text: str, query: str, k: int = 3) -> list[dict]:
    """Return the k paragraphs most similar to the query, with their index."""
    paras = split_paragraphs(policy_text)
    if not paras:
        return []
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
    matrix = vec.fit_transform(paras + [query])
    scores = linear_kernel(matrix[-1], matrix[:-1]).ravel()
    order = scores.argsort()[::-1][:k]
    return [{"paragraph": int(i), "score": float(scores[i]), "text": paras[i]} for i in order if scores[i] > 0]
