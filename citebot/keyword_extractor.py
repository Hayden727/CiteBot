"""Keyword extraction with LLM-first strategy and NLP ensemble fallback."""

from __future__ import annotations

import json
import logging
import os
import re
from collections import defaultdict

import httpx

from citebot.types import ExtractedKeywords, KeywordExtractionError, TexDocument, TexProject

logger = logging.getLogger(__name__)

# Ensemble weights (used in fallback mode)
_WEIGHT_KEYBERT = 0.5
_WEIGHT_YAKE = 0.3
_WEIGHT_SPACY = 0.2

# LLM API timeout: generous read timeout for long document analysis
_LLM_TIMEOUT = httpx.Timeout(connect=15.0, read=180.0, write=15.0, pool=15.0)


def extract_keywords(document: TexDocument, top_n: int = 15) -> ExtractedKeywords:
    """Extract keywords from a single TeX document.

    Strategy: Fuse LLM (domain understanding) with NLP (term frequency).
    Falls back to NLP-only if LLM is unavailable.

    Raises:
        KeywordExtractionError: If all methods fail.
    """
    text = _build_weighted_text(document)
    if not text.strip():
        raise KeywordExtractionError("No text available for keyword extraction")

    llm_result = _try_llm_extraction(document.title, text, top_n)
    if llm_result is not None:
        return _fuse_llm_and_nlp(llm_result, text, top_n)

    logger.info("LLM extraction unavailable, using NLP ensemble fallback")
    return _extract_ensemble(text, top_n)


def extract_keywords_from_project(
    project: TexProject, top_n: int = 15,
) -> ExtractedKeywords:
    """Extract keywords from a multi-file LaTeX project.

    For large projects (>6000 chars), extracts keywords from each chapter
    separately via LLM, then merges and deduplicates.

    Raises:
        KeywordExtractionError: If all methods fail.
    """
    combined_text = project.combined_full_text
    if not combined_text.strip():
        raise KeywordExtractionError("No text available for keyword extraction")

    # For single-file or small projects, use standard extraction with fusion
    if not project.is_multi_file or len(combined_text) <= 8000:
        llm_result = _try_llm_extraction(project.combined_title, combined_text, top_n)
        if llm_result is not None:
            return _fuse_llm_and_nlp(llm_result, combined_text, top_n)
        return _extract_ensemble(combined_text, top_n)

    # --- Multi-file context-aware LLM extraction ---
    api_key, base_url, model = _resolve_llm_config()
    if not api_key:
        logger.info("No LLM API for chunked extraction, using ensemble on combined text")
        return _extract_ensemble(combined_text[:100_000], top_n)

    # Step 1: LLM generates a project summary for global context
    project_summary = _generate_project_summary(project, api_key, base_url, model)

    # Step 2: Extract per-chapter keywords with cumulative context
    all_keywords: dict[str, float] = defaultdict(float)
    extracted_so_far: list[str] = []
    n_chunks = 0

    for doc in project.all_docs:
        if not doc.full_text or len(doc.full_text.strip()) < 100:
            continue

        chapter_title = doc.title or "Untitled Chapter"
        per_chapter_n = max(top_n // max(len(project.all_docs), 1), 10)

        result = _try_llm_context_extraction(
            project_title=project.combined_title,
            project_summary=project_summary,
            chapter_title=chapter_title,
            chapter_text=doc.full_text,
            existing_keywords=extracted_so_far,
            top_n=per_chapter_n,
            api_key=api_key,
            base_url=base_url,
            model=model,
        )
        if result is not None:
            n_chunks += 1
            for kw, score in result.keywords:
                key = kw.lower().strip()
                all_keywords[key] = max(all_keywords[key], score)
                if key not in extracted_so_far:
                    extracted_so_far.append(key)
            logger.debug(
                "Chapter %r: %d keywords", chapter_title[:30], len(result.keywords)
            )

    if not all_keywords:
        logger.warning("Chunked LLM extraction returned nothing, falling back to ensemble")
        return _extract_ensemble(combined_text[:100_000], top_n)

    # Re-rank by searchability and take top_n
    ranked = _rerank_by_searchability(all_keywords)[:top_n]
    logger.info(
        "Merged keywords from %d chapters: %d unique -> top %d",
        n_chunks, len(all_keywords), len(ranked),
    )
    return ExtractedKeywords(keywords=tuple(ranked), source_method="llm")


# ---------------------------------------------------------------------------
# LLM-based extraction
# ---------------------------------------------------------------------------

_LLM_PROMPT_TEMPLATE = """You are an academic search query expert. Given a LaTeX document, generate search terms to find EXISTING related papers in academic databases.

Document title: {title}

Document content (excerpt):
{text}

CRITICAL DISTINCTION:
- Do NOT describe what this document does (its unique contributions or novelty)
- DO identify the established research areas, tools, frameworks, and techniques it builds upon
- Think: "What papers would the author cite in the Related Work section?"

Requirements:
1. Extract exactly {top_n} search terms
2. Terms MUST be in English (translate if the document is in another language)
3. Prefer SHORT, CONCRETE terms that appear frequently in paper titles:
   - GOOD: "graph neural network", "batch normalization", "Monte Carlo simulation"
   - BAD: "our novel optimization strategy", "proposed hybrid framework for X"
4. Include a mix of:
   - Named tools/frameworks/datasets used in the field
   - Established techniques and algorithms
   - Research subfields and problem domains
5. Each term should be 1-3 words (max 4 only if it is a well-known phrase)
6. Order by search priority (most important first)

Return ONLY a JSON array of strings, no explanation."""

_LLM_SUMMARY_PROMPT_TEMPLATE = """You are an academic document analyst. Read the following multi-chapter LaTeX project and produce a concise research summary.

Project title: {title}

Document content (combined excerpt from all chapters):
{text}

Produce a summary (200-400 words) covering:
1. The main research topic and objectives
2. Key methods, algorithms, or frameworks used
3. The domain and subfields involved
4. Core contributions or findings

Write the summary in English. Be specific about technical terms — these will be used to guide keyword extraction for academic database searches."""

_LLM_CONTEXT_PROMPT_TEMPLATE = """You are an academic search query expert analyzing a chapter from a multi-file LaTeX project.

Project title: {project_title}

Project summary:
{project_summary}

Keywords already extracted from previous chapters:
{existing_keywords}

Current chapter: {chapter_title}

Chapter content (excerpt):
{text}

IMPORTANT: Generate terms that will FIND EXISTING PAPERS, not describe this chapter's contribution.
Ask yourself: "What would I type into Google Scholar to find papers related to this chapter?"

Requirements:
1. Extract exactly {top_n} NEW search terms from this chapter
2. DO NOT repeat any keywords from the "already extracted" list above — find complementary terms
3. Terms MUST be in English (translate if the document is in another language)
4. Prefer short, concrete terms (1-3 words) that appear in paper titles
5. Include named tools, frameworks, established techniques, and research subfields
6. Consider the project context to identify domain-specific terms
7. Order by search priority (most important first)

Return ONLY a JSON array of strings, no explanation."""


def _llm_chat(
    api_key: str,
    base_url: str,
    model: str,
    prompt: str,
    max_tokens: int = 1024,
) -> str | None:
    """Send a chat completion request to an OpenAI-compatible API.

    Returns the response content string, or None on failure.
    """
    try:
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
                "max_tokens": max_tokens,
            },
            timeout=_LLM_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.warning("LLM API call failed: %s", exc)
        return None


def _generate_project_summary(
    project: TexProject,
    api_key: str,
    base_url: str,
    model: str,
) -> str:
    """Use LLM to generate a research summary of the entire project.

    Collects excerpts from each chapter and asks the LLM to produce
    a concise summary that captures the project's scope and methods.
    Returns empty string on failure (non-critical).
    """
    chapter_excerpts: list[str] = []
    for doc in project.all_docs:
        if not doc.full_text or len(doc.full_text.strip()) < 100:
            continue
        label = doc.title or "Untitled"
        chapter_excerpts.append(f"[{label}]\n{doc.full_text[:2000]}")

    combined_excerpt = "\n\n---\n\n".join(chapter_excerpts)[:12000]

    prompt = _LLM_SUMMARY_PROMPT_TEMPLATE.format(
        title=project.combined_title,
        text=combined_excerpt,
    )

    logger.info("Generating project summary via LLM...")
    content = _llm_chat(api_key, base_url, model, prompt, max_tokens=1024)
    if content:
        logger.info("Project summary generated (%d chars)", len(content))
        return content

    logger.warning("Failed to generate project summary, continuing without it")
    return ""


def _try_llm_extraction(
    title: str,
    full_text: str,
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

    prompt = _LLM_PROMPT_TEMPLATE.format(
        title=title,
        text=full_text[:6000],
        top_n=top_n,
    )

    content = _llm_chat(api_key, base_url, model, prompt)
    if content is None:
        return None

    keywords = _parse_llm_response(content, top_n)
    if keywords:
        logger.info("LLM extracted %d keywords: %s", len(keywords), keywords[:5])
        scored = tuple(
            (kw, 1.0 - i / len(keywords))
            for i, kw in enumerate(keywords)
        )
        return ExtractedKeywords(keywords=scored, source_method="llm")

    return None


def _try_llm_context_extraction(
    project_title: str,
    project_summary: str,
    chapter_title: str,
    chapter_text: str,
    existing_keywords: list[str],
    top_n: int,
    api_key: str,
    base_url: str,
    model: str,
) -> ExtractedKeywords | None:
    """Extract keywords from a chapter with project context and dedup awareness."""
    kw_display = ", ".join(existing_keywords) if existing_keywords else "(none yet)"

    prompt = _LLM_CONTEXT_PROMPT_TEMPLATE.format(
        project_title=project_title,
        project_summary=project_summary or "(summary unavailable)",
        existing_keywords=kw_display,
        chapter_title=chapter_title,
        text=chapter_text[:6000],
        top_n=top_n,
    )

    content = _llm_chat(api_key, base_url, model, prompt)
    if content is None:
        return None

    keywords = _parse_llm_response(content, top_n)
    if keywords:
        logger.info(
            "LLM context-extracted %d keywords from %r: %s",
            len(keywords), chapter_title[:30], keywords[:5],
        )
        scored = tuple(
            (kw, 1.0 - i / len(keywords))
            for i, kw in enumerate(keywords)
        )
        return ExtractedKeywords(keywords=scored, source_method="llm")

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

def _strip_non_latin(text: str) -> str:
    """Remove non-Latin characters (Chinese, Japanese, etc.) for English NLP models.

    Keeps ASCII, Latin-extended, common punctuation, and whitespace.
    """
    cleaned = re.sub(r"[^\u0000-\u024F\s.,;:!?()'\"-]", " ", text)
    # Collapse multiple spaces
    return re.sub(r"\s{2,}", " ", cleaned).strip()


def _extract_ensemble(text: str, top_n: int) -> ExtractedKeywords:
    """Fall back to NLP ensemble when LLM is unavailable.

    Strips non-Latin text first since KeyBERT/YAKE/spaCy are English models.
    """
    clean_text = _strip_non_latin(text)
    if len(clean_text) < 100:
        raise KeywordExtractionError(
            "Not enough English text for NLP keyword extraction"
        )

    results: dict[str, list[tuple[str, float]]] = {}
    errors: list[str] = []

    for name, fn in (
        ("keybert", _extract_keybert),
        ("yake", _extract_yake),
        ("spacy", _extract_spacy_noun_phrases),
    ):
        try:
            results[name] = fn(clean_text, top_n=top_n)
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


_FUSION_WEIGHT_LLM = 0.6
_FUSION_WEIGHT_NLP = 0.4
_FUSION_OVERLAP_BOOST = 1.5


def _fuse_llm_and_nlp(
    llm_result: ExtractedKeywords,
    text: str,
    top_n: int,
) -> ExtractedKeywords:
    """Fuse LLM keywords (domain understanding) with NLP keywords (term frequency).

    Keywords appearing in both sources get a 1.5x boost.
    Returns LLM result unchanged if NLP ensemble fails.
    """
    try:
        nlp_result = _extract_ensemble(text, top_n)
    except KeywordExtractionError:
        logger.info("NLP ensemble failed during fusion, returning LLM-only result")
        return llm_result

    merged: dict[str, float] = defaultdict(float)

    for kw, score in llm_result.keywords:
        merged[kw.lower().strip()] += _FUSION_WEIGHT_LLM * score
    for kw, score in nlp_result.keywords:
        merged[kw.lower().strip()] += _FUSION_WEIGHT_NLP * score

    # Boost keywords found in both sources
    llm_set = {kw.lower().strip() for kw, _ in llm_result.keywords}
    nlp_set = {kw.lower().strip() for kw, _ in nlp_result.keywords}
    for kw in llm_set & nlp_set:
        merged[kw] *= _FUSION_OVERLAP_BOOST

    reranked = _rerank_by_searchability(merged)
    top = reranked[:top_n]
    logger.info(
        "Fused %d LLM + %d NLP keywords -> %d (overlap: %d boosted)",
        len(llm_result.keywords), len(nlp_result.keywords),
        len(top), len(llm_set & nlp_set),
    )
    return ExtractedKeywords(keywords=tuple(top), source_method="llm+nlp")


def _rerank_by_searchability(
    scored: dict[str, float],
) -> list[tuple[str, float]]:
    """Re-rank keywords by searchability: boost terms likely to return results.

    Heuristic multipliers:
      - All-uppercase (acronyms like MLIR, GAN): 1.4x — almost always searchable
      - Short terms (≤6 chars): 1.2x — likely established names
      - 2-3 word phrases: 1.0x — neutral
      - Long single words (>10 chars): 0.7x — often niche/internal
      - Long phrases (>4 words): 0.7x — too specific for search
    """
    adjusted: list[tuple[str, float]] = []
    for kw, score in scored.items():
        words = kw.split()
        word_count = len(words)

        if word_count == 1:
            if kw.isupper():
                multiplier = 1.4
            elif len(kw) <= 6:
                multiplier = 1.2
            elif len(kw) > 10:
                multiplier = 0.7
            else:
                multiplier = 1.0
        elif word_count > 4:
            multiplier = 0.7
        else:
            multiplier = 1.0

        adjusted.append((kw, score * multiplier))

    adjusted.sort(key=lambda x: x[1], reverse=True)
    return adjusted


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
