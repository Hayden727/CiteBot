"""Keyword extraction with LLM-first strategy and NLP ensemble fallback."""

from __future__ import annotations

import json
import logging
import os
import re
from collections import defaultdict

from citebot.types import ExtractedKeywords, KeywordExtractionError, TexDocument

logger = logging.getLogger(__name__)

# Ensemble weights (used in fallback mode)
_WEIGHT_KEYBERT = 0.5
_WEIGHT_YAKE = 0.3
_WEIGHT_SPACY = 0.2


def extract_keywords(document: TexDocument, top_n: int = 15) -> ExtractedKeywords:
    """Extract keywords from a parsed TeX document.

    Strategy:
      1. Try LLM extraction first (best for multilingual / domain-specific docs)
      2. Fall back to NLP ensemble (KeyBERT + YAKE + spaCy)

    Raises:
        KeywordExtractionError: If all methods fail.
    """
    text = _build_weighted_text(document)
    if not text.strip():
        raise KeywordExtractionError("No text available for keyword extraction")

    # --- Strategy 1: LLM extraction (preferred) ---
    llm_result = _try_llm_extraction(document, top_n)
    if llm_result is not None:
        return llm_result

    # --- Strategy 2: NLP ensemble fallback ---
    logger.info("LLM extraction unavailable, using NLP ensemble fallback")
    return _extract_ensemble(text, top_n)


# ---------------------------------------------------------------------------
# LLM-based extraction
# ---------------------------------------------------------------------------

_LLM_PROMPT_TEMPLATE = """You are an academic keyword extraction expert. Analyze the following LaTeX document content and extract the most important technical keywords and phrases for searching academic papers.

Document title: {title}

Document content (excerpt):
{text}

Requirements:
1. Extract exactly {top_n} keywords/phrases
2. Keywords MUST be in English (translate if the document is in another language)
3. Focus on technical terms, methods, algorithms, and domain concepts
4. Keywords should be suitable for searching academic databases (Semantic Scholar, arXiv, etc.)
5. Order by relevance (most important first)
6. Each keyword should be 1-4 words

Return ONLY a JSON array of strings, no explanation. Example: ["deep learning", "transformer architecture", "attention mechanism"]"""


def _try_llm_extraction(
    document: TexDocument,
    top_n: int,
) -> ExtractedKeywords | None:
    """Try to extract keywords using an LLM API.

    Supports OpenAI-compatible APIs via OPENAI_API_KEY + OPENAI_BASE_URL,
    or DEEPSEEK_API_KEY for DeepSeek.

    Returns None if no API key is configured.
    """
    api_key, base_url, model = _resolve_llm_config()
    if not api_key:
        logger.debug("No LLM API key configured, skipping LLM extraction")
        return None

    try:
        import httpx

        # Build prompt with truncated text
        text_excerpt = document.full_text[:6000]
        prompt = _LLM_PROMPT_TEMPLATE.format(
            title=document.title,
            text=text_excerpt,
            top_n=top_n,
        )

        response = httpx.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 1024,
            },
            timeout=30.0,
        )
        response.raise_for_status()

        content = response.json()["choices"][0]["message"]["content"].strip()
        keywords = _parse_llm_response(content, top_n)

        if keywords:
            logger.info("LLM extracted %d keywords: %s", len(keywords), keywords[:5])
            scored = tuple(
                (kw, 1.0 - i / len(keywords))
                for i, kw in enumerate(keywords)
            )
            return ExtractedKeywords(keywords=scored, source_method="llm")

    except Exception as exc:
        logger.warning("LLM extraction failed: %s", exc)

    return None


def _resolve_llm_config() -> tuple[str, str, str]:
    """Resolve LLM API configuration from environment variables.

    Priority:
      1. OPENAI_API_KEY + OPENAI_BASE_URL + OPENAI_MODEL
      2. DEEPSEEK_API_KEY (uses DeepSeek API)

    Returns (api_key, base_url, model) or ("", "", "") if unconfigured.
    """
    # OpenAI-compatible API
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key:
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        return openai_key, base_url, model

    # DeepSeek API
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if deepseek_key:
        return deepseek_key, "https://api.deepseek.com/v1", "deepseek-chat"

    return "", "", ""


def _parse_llm_response(content: str, top_n: int) -> list[str]:
    """Parse LLM response into a list of keyword strings."""
    # Try to find JSON array in the response
    match = re.search(r"\[.*\]", content, re.DOTALL)
    if not match:
        return []

    try:
        raw = json.loads(match.group())
        if isinstance(raw, list):
            keywords = [str(k).strip() for k in raw if isinstance(k, str) and k.strip()]
            return keywords[:top_n]
    except json.JSONDecodeError:
        pass

    return []


# ---------------------------------------------------------------------------
# NLP ensemble fallback
# ---------------------------------------------------------------------------

def _extract_ensemble(text: str, top_n: int) -> ExtractedKeywords:
    """Fall back to NLP ensemble when LLM is unavailable."""
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

    if len(results) == 1:
        method = next(iter(results))
        kws = results[method][:top_n]
        return ExtractedKeywords(keywords=tuple(kws), source_method=method)

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
    if document.title:
        parts.extend([document.title] * 3)
    if document.abstract:
        parts.extend([document.abstract] * 2)
    for _heading, body in document.sections:
        parts.append(body)
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Individual NLP extractors
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
    return [(kw, float(score)) for kw, score in raw]


def _extract_yake(text: str, top_n: int) -> list[tuple[str, float]]:
    """YAKE: unsupervised statistical keyword extraction."""
    import yake

    extractor = yake.KeywordExtractor(lan="en", n=3, top=top_n)
    raw = extractor.extract_keywords(text)
    return _normalize_yake_scores(raw)


def _extract_spacy_noun_phrases(text: str, top_n: int) -> list[tuple[str, float]]:
    """spaCy: extract noun phrases scored by frequency."""
    import spacy

    nlp = spacy.load("en_core_web_sm")
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
# Score normalization & merging
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
    """Merge keyword results from all extractors with weighted scoring."""
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

    ranked = sorted(combined.items(), key=lambda x: x[1], reverse=True)
    return tuple(ranked[:top_n])
