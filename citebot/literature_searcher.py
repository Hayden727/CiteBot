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


def _build_search_queries(
    keywords: ExtractedKeywords,
    max_queries: int = 5,
) -> tuple[str, ...]:
    """Build search queries of varying specificity from keywords.

    Strategy:
      - Query 1: Top 3 keywords combined (broad)
      - Query 2-3: Pairs of top keywords (medium)
      - Query 4-5: Individual high-scoring keywords (targeted)
    """
    kw_list = [kw for kw, _score in keywords.keywords]
    if not kw_list:
        return ()

    queries: list[str] = []

    # Broad: top 3 combined
    if len(kw_list) >= 3:
        queries.append(" ".join(kw_list[:3]))
    elif kw_list:
        queries.append(" ".join(kw_list))

    # Medium: pairs
    pairs = [(0, 1), (0, 2), (1, 2)]
    for i, j in pairs:
        if j < len(kw_list) and len(queries) < max_queries:
            queries.append(f"{kw_list[i]} {kw_list[j]}")

    # Targeted: individual keywords (skip those already in combined)
    for kw in kw_list[3:6]:
        if len(queries) < max_queries:
            queries.append(kw)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique.append(q)

    return tuple(unique[:max_queries])
