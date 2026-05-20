"""Text and citation scoring utilities."""

from __future__ import annotations

from functools import lru_cache

import pandas as pd


@lru_cache(maxsize=1)
def _spacy_nlp():
    from spacy.lang.en import English

    nlp = English()
    nlp.add_pipe("lemmatizer", config={"mode": "rule"})
    nlp.initialize()
    return nlp


@lru_cache(maxsize=1)
def _stopwords() -> set[str]:
    from spacy.lang.en.stop_words import STOP_WORDS

    return {word.lower() for word in STOP_WORDS}


@lru_cache(maxsize=200_000)
def _lemmatize_cached(text: str) -> tuple[str, ...]:
    nlp = _spacy_nlp()
    stopwords = _stopwords()
    doc = nlp(text)
    out = []
    for token in doc:
        lemma = (token.lemma_ or "").strip().lower()
        if lemma and not token.is_punct and lemma not in stopwords:
            out.append(lemma)
    return tuple(out)


@lru_cache(maxsize=1)
def _sbert_model():
    import torch
    from sentence_transformers import SentenceTransformer

    device = "mps" if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available() else "cpu"
    return SentenceTransformer("all-MiniLM-L6-v2", device=device)


def word_overlap_score(a: object, b: object) -> float | None:
    if a is None or b is None or pd.isna(a) or pd.isna(b):
        return None
    set_a = set(_lemmatize_cached(str(a)))
    set_b = set(_lemmatize_cached(str(b)))
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / min(len(set_a), len(set_b))


def semantic_similarity_score(a: object, b: object) -> float | None:
    if a is None or b is None or pd.isna(a) or pd.isna(b):
        return None
    from sentence_transformers import util

    model = _sbert_model()
    embeddings = model.encode([str(a), str(b)], convert_to_tensor=True)
    score = util.cos_sim(embeddings[0], embeddings[1])
    return float(score.cpu().numpy()[0][0])


def citation_overlap_score(patent_ids: object, work_ids: object) -> float | None:
    if not isinstance(patent_ids, list) or not isinstance(work_ids, list):
        return None
    pat = {x.lower() if isinstance(x, str) else x for x in patent_ids if x}
    work = {x.lower() if isinstance(x, str) else x for x in work_ids if x}
    if not pat or not work:
        return None
    return len(pat & work) / len(pat)
