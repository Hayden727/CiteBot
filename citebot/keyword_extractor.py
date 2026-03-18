"""Ensemble keyword extraction using KeyBERT, YAKE, and spaCy."""

from __future__ import annotations

import logging
from collections import defaultdict

from citebot.types import ExtractedKeywords, KeywordExtractionError, TexDocument

logger = logging.getLogger(__name__)

# Ensemble weights
_WEIGHT_KEYBERT = 0.5
_WEIGHT_YAKE = 0.3
_WEIGHT_SPACY = 0.2


def extract_keywords(document: TexDocument, top_n: int = 15) -> ExtractedKeywords:
    """Extract keywords from a parsed TeX document using an ensemble approach.

    Combines KeyBERT (semantic), YAKE (statistical), and spaCy (noun phrases).
    The document title and abstract are weighted more heavily in the input text.

    Raises:
        KeywordExtractionError: If all extractors fail.
    """
    text = _build_weighted_text(document)
    if not text.strip():
        raise KeywordExtractionError("No text available for keyword extraction")

    results: dict[str, list[tuple[str, float]]] = {}
    errors: list[str] = []

    for name, fn in (
        ("keybert", _extract_keybert),
        ("yake", _extract_yake),
        ("spacy", _extract_spacy_noun_phrases),
    ):
        try:
            results[name] = fn(text, top_n=top_n)
            logger.debug("%s returned %d keywords", name, len(results[name]))
        except Exception as exc:
            logger.warning("%s extraction failed: %s", name, exc)
            errors.append(f"{name}: {exc}")

    if not results:
        raise KeywordExtractionError(
            f"All keyword extractors failed: {'; '.join(errors)}"
        )

    # If only one extractor succeeded, use it directly
    if len(results) == 1:
        method = next(iter(results))
        kws = results[method][:top_n]
        return ExtractedKeywords(
            keywords=tuple(kws),
            source_method=method,
        )

    merged = _ensemble_merge(
        keybert_kw=results.get("keybert", []),
        yake_kw=results.get("yake", []),
        spacy_kw=results.get("spacy", []),
        top_n=top_n,
    )

    logger.info("Extracted %d keywords (ensemble)", len(merged))
    return ExtractedKeywords(keywords=merged, source_method="ensemble")


def _build_weighted_text(document: TexDocument) -> str:
    """Build input text with title and abstract weighted higher."""
    parts: list[str] = []
    # Title repeated 3x for emphasis
    if document.title:
        parts.extend([document.title] * 3)
    # Abstract repeated 2x
    if document.abstract:
        parts.extend([document.abstract] * 2)
    # Section text
    for _heading, body in document.sections:
        parts.append(body)
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Individual extractors
# ---------------------------------------------------------------------------

def _extract_keybert(text: str, top_n: int) -> list[tuple[str, float]]:
    """KeyBERT: semantic keyword extraction via sentence embeddings."""
    from keybert import KeyBERT

    model = KeyBERT()
    raw = model.extract_keywords(
        text,
        keyphrase_ngram_range=(1, 3),
        stop_words="english",
        top_n=top_n,
        use_mmr=True,
        diversity=0.5,
    )
    # raw is list[(str, float)] with scores in [0, 1]
    return [(kw, float(score)) for kw, score in raw]


def _extract_yake(text: str, top_n: int) -> list[tuple[str, float]]:
    """YAKE: unsupervised statistical keyword extraction.

    YAKE scores are inverted (lower = more relevant),
    so we normalize to 0-1 where higher = better.
    """
    import yake

    extractor = yake.KeywordExtractor(lan="en", n=3, top=top_n)
    raw = extractor.extract_keywords(text)
    return _normalize_yake_scores(raw)


def _extract_spacy_noun_phrases(text: str, top_n: int) -> list[tuple[str, float]]:
    """spaCy: extract noun phrases scored by frequency."""
    import spacy

    nlp = spacy.load("en_core_web_sm")
    # Limit text length to avoid memory issues
    doc = nlp(text[:100_000])

    phrase_counts: dict[str, int] = defaultdict(int)
    for chunk in doc.noun_chunks:
        phrase = chunk.text.lower().strip()
        if len(phrase) > 2 and not phrase.isnumeric():
            phrase_counts[phrase] += 1

    if not phrase_counts:
        return []

    max_count = max(phrase_counts.values())
    scored = [
        (phrase, count / max_count) for phrase, count in phrase_counts.items()
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_n]


# ---------------------------------------------------------------------------
# Ensemble merging
# ---------------------------------------------------------------------------

def _normalize_yake_scores(
    raw: list[tuple[str, float]],
) -> list[tuple[str, float]]:
    """Convert YAKE scores (lower=better) to higher=better in [0, 1]."""
    if not raw:
        return []
    max_score = max(score for _, score in raw) or 1.0
    return [(kw, 1.0 - (score / max_score)) for kw, score in raw]


def _ensemble_merge(
    keybert_kw: list[tuple[str, float]],
    yake_kw: list[tuple[str, float]],
    spacy_kw: list[tuple[str, float]],
    top_n: int,
) -> tuple[tuple[str, float], ...]:
    """Merge keyword results from all extractors with weighted scoring.

    Deduplicates by lowercased keyword. Returns top_n sorted desc by score.
    """
    combined: dict[str, float] = defaultdict(float)

    for kw_list, weight in (
        (keybert_kw, _WEIGHT_KEYBERT),
        (yake_kw, _WEIGHT_YAKE),
        (spacy_kw, _WEIGHT_SPACY),
    ):
        for keyword, score in kw_list:
            normalized_key = keyword.lower().strip()
            if normalized_key:
                combined[normalized_key] += weight * score

    # Sort by combined score descending
    ranked = sorted(combined.items(), key=lambda x: x[1], reverse=True)
    return tuple(ranked[:top_n])
