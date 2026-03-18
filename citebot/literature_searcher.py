"""Async literature search via OpenCite SearchOrchestrator."""

from __future__ import annotations

import asyncio
import logging

from opencite.config import Config as OpenCiteConfig
from opencite.models import Paper
from opencite.search import SearchOrchestrator

from citebot.config import CiteConfig
from citebot.types import ExtractedKeywords, SearchError

logger = logging.getLogger(__name__)


async def search_papers(
    keywords: ExtractedKeywords,
    config: CiteConfig,
) -> list[Paper]:
    """Search for papers using extracted keywords across multiple sources.

    Builds multiple queries of varying specificity and runs them in parallel.
    Returns the combined (undeduped) list of papers.

    Raises:
        SearchError: If all queries fail.
    """
    queries = _build_search_queries(keywords, max_queries=5)
    if not queries:
        raise SearchError("No search queries could be built from keywords")

    logger.info("Searching with %d queries across %s", len(queries), config.sources)

    all_papers: list[Paper] = []
    errors: list[str] = []

    async with SearchOrchestrator(config.opencite_config) as searcher:
        tasks = [
            _search_single_query(searcher, query, config)
            for query in queries
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    for query, result in zip(queries, results):
        if isinstance(result, Exception):
            logger.warning("Query %r failed: %s", query, result)
            errors.append(f"{query}: {result}")
        elif result:
            all_papers.extend(result)
            logger.debug("Query %r returned %d papers", query, len(result))
        else:
            logger.debug("Query %r returned no results", query)

    if not all_papers:
        error_detail = "; ".join(errors) if errors else "no results from any query"
        raise SearchError(f"Search returned no papers: {error_detail}")

    logger.info("Total raw results: %d papers from %d queries", len(all_papers), len(queries))
    return all_papers


async def _search_single_query(
    searcher: SearchOrchestrator,
    query: str,
    config: CiteConfig,
) -> list[Paper]:
    """Execute a single search query with error handling."""
    try:
        result = await searcher.search(
            query=query,
            max_results=config.num_refs,
            sources=config.sources,
            year_from=config.year_from,
            year_to=config.year_to,
            sort="relevance",
        )
        return list(result.papers)
    except Exception as exc:
        logger.warning("Search query failed: %r -> %s", query, exc)
        raise


def _quote_phrase(kw: str) -> str:
    """Wrap multi-word keywords in quotes so APIs treat them as exact phrases."""
    return f'"{kw}"' if " " in kw else kw


# Generic single words that match too many unrelated papers
_GENERIC_SINGLE_WORDS = frozenset({
    "model", "method", "system", "data", "analysis", "approach",
    "framework", "network", "algorithm", "process", "technique",
    "structure", "function", "performance", "evaluation", "results",
    "study", "research", "review", "survey", "design", "code",
    "learning", "training", "prediction", "detection", "generation",
    "optimization", "implementation", "application", "comparison",
    "based", "using", "novel", "new", "improved", "efficient",
})


def _broad_priority(word: str) -> tuple[int, int]:
    """Sort key: prefer well-known terms for broad queries.

    Priority order (lower = better):
      1. All-uppercase acronyms — most searchable
      2. Short terms (≤6 chars) — likely established names
      3. Everything else — niche/internal terms
    Within each tier, shorter words come first.
    """
    if word.isupper():
        tier = 0
    elif len(word) <= 6:
        tier = 1
    else:
        tier = 2
    return (tier, len(word))


def _is_technical_term(word: str) -> bool:
    """Heuristic: is this single word specific enough to search alone?

    Accepts acronyms, short technical terms, and domain-specific
    words not in the generic set.
    """
    return len(word) > 2 and word.lower() not in _GENERIC_SINGLE_WORDS


def _build_search_queries(
    keywords: ExtractedKeywords,
    max_queries: int = 5,
) -> tuple[str, ...]:
    """Build search queries with three tiers of specificity.

    Scales max_queries based on keyword count:
      - <=15 keywords: up to 5 queries (default)
      - >15 keywords: up to max(5, num_keywords // 3) queries

    Strategy:
      1. Broad: top short keywords unquoted (high recall)
      2. Medium: short keyword + quoted phrase (balanced)
      3. Targeted: individual quoted phrases (high precision)
      4. Technical singles: domain-specific single words
    """
    kw_list = [kw for kw, _score in keywords.keywords]
    if not kw_list:
        return ()

    # Scale queries for large keyword sets
    if len(kw_list) > 15:
        max_queries = max(max_queries, len(kw_list) // 3)

    # Classify keywords
    short_kws = [kw for kw in kw_list if " " not in kw]
    phrase_kws = [kw for kw in kw_list if " " in kw]

    # Sort short keywords: prefer well-known terms (shorter, uppercase/acronyms)
    # for broad queries; longer/niche terms go to targeted queries
    broad_shorts = sorted(short_kws, key=_broad_priority)
    # Sort phrases: shorter phrases first (more likely to be established terms)
    broad_phrases = sorted(phrase_kws, key=len)

    queries: list[str] = []

    # Tier 1 — Broad: most general short keywords unquoted (high recall)
    if broad_shorts:
        queries.append(" ".join(broad_shorts[:3]))

    # Tier 2 — Medium: general short keyword + quoted phrase (balanced)
    for s in broad_shorts[:3]:
        for p in broad_phrases[:3]:
            if len(queries) < max_queries:
                queries.append(f"{s} {_quote_phrase(p)}")

    # Tier 3 — Targeted: individual quoted phrases (high precision)
    for p in phrase_kws:
        if len(queries) < max_queries:
            queries.append(_quote_phrase(p))

    # Tier 4 — Technical singles: domain-specific single words
    for s in short_kws:
        if len(queries) < max_queries and _is_technical_term(s):
            queries.append(s)

    # Fallback: if no short keywords, use top phrases unquoted
    if not queries and phrase_kws:
        queries.append(" ".join(phrase_kws[:3]))

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique.append(q)

    return tuple(unique[:max_queries])
