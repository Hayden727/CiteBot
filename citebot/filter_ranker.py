"""Deduplicate and rank search results by composite relevance score."""

from __future__ import annotations

import logging
import math
import re
import unicodedata
from datetime import datetime

from opencite.models import Paper
from rapidfuzz import fuzz

from citebot.types import ExtractedKeywords, ScoredPaper, TexDocument

logger = logging.getLogger(__name__)

# Scoring weights
_W_KEYWORD = 0.40
_W_CITATION = 0.25
_W_RECENCY = 0.20
_W_ABSTRACT = 0.15

# Dedup threshold for title similarity
_TITLE_SIMILARITY_THRESHOLD = 90

# Citation score normalization (log scale)
_MAX_EXPECTED_CITATIONS = 10_000

# Recency decay constant (half-life ~5 years)
_RECENCY_DECAY = 0.14


def filter_and_rank(
    papers: list[Paper],
    keywords: ExtractedKeywords,
    document: TexDocument,
    num_refs: int,
) -> tuple[ScoredPaper, ...]:
    """Deduplicate, score, and rank papers. Returns top num_refs results.

    Never mutates the input list.
    """
    if not papers:
        return ()

    deduped = _deduplicate_papers(papers)
    logger.info("After dedup: %d papers (from %d raw)", len(deduped), len(papers))

    current_year = datetime.now().year
    existing_keys: set[str] = set(document.existing_cite_keys)

    scored: list[ScoredPaper] = []
    for paper in deduped:
        sp = _score_paper(paper, keywords, document, current_year, existing_keys)
        scored.append(sp)
        existing_keys.add(sp.cite_key)

    scored.sort(key=lambda s: s.relevance_score, reverse=True)
    top = tuple(scored[:num_refs])

    logger.info(
        "Ranked %d papers, returning top %d (scores %.3f - %.3f)",
        len(scored),
        len(top),
        top[0].relevance_score if top else 0,
        top[-1].relevance_score if top else 0,
    )
    return top


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _deduplicate_papers(papers: list[Paper]) -> list[Paper]:
    """Remove duplicate papers by DOI and fuzzy title matching."""
    seen_dois: set[str] = set()
    seen_titles: list[str] = []
    unique: list[Paper] = []

    for paper in papers:
        # DOI-based dedup (most reliable)
        doi = getattr(paper.ids, "doi", None) or "" if hasattr(paper, "ids") else ""
        if doi:
            if doi.lower() in seen_dois:
                continue
            seen_dois.add(doi.lower())

        # Title-based fuzzy dedup
        title = (paper.title or "").strip()
        if title and _is_title_duplicate(title, seen_titles):
            continue

        if title:
            seen_titles.append(title)
        unique.append(paper)

    return unique


def _is_title_duplicate(title: str, existing: list[str]) -> bool:
    """Check if a title is a near-duplicate of any existing title."""
    for existing_title in existing:
        if fuzz.ratio(title.lower(), existing_title.lower()) >= _TITLE_SIMILARITY_THRESHOLD:
            return True
    return False


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score_paper(
    paper: Paper,
    keywords: ExtractedKeywords,
    document: TexDocument,
    current_year: int,
    existing_keys: set[str],
) -> ScoredPaper:
    """Compute composite relevance score for a paper."""
    kw_score = _compute_keyword_overlap(paper, keywords)
    rec_score = _compute_recency_score(paper.year, current_year)
    cit_score = _compute_citation_score(paper.citation_count or 0)
    abs_score = _compute_abstract_match(paper, document)

    total = (
        _W_KEYWORD * kw_score
        + _W_CITATION * cit_score
        + _W_RECENCY * rec_score
        + _W_ABSTRACT * abs_score
    )

    cite_key = _make_unique_cite_key(paper, existing_keys)

    return ScoredPaper(
        paper=paper,
        relevance_score=total,
        keyword_overlap=kw_score,
        recency_score=rec_score,
        citation_score=cit_score,
        cite_key=cite_key,
    )


def _compute_keyword_overlap(
    paper: Paper,
    keywords: ExtractedKeywords,
) -> float:
    """Fraction of extracted keywords found in paper title + abstract."""
    paper_text = " ".join(
        filter(None, [paper.title, paper.abstract])
    ).lower()
    if not paper_text:
        return 0.0

    matches = 0
    total = len(keywords.keywords)
    if total == 0:
        return 0.0

    for kw, _score in keywords.keywords:
        kw_lower = kw.lower()
        # Exact substring match or fuzzy match
        if kw_lower in paper_text:
            matches += 1
        elif fuzz.partial_ratio(kw_lower, paper_text) >= 85:
            matches += 0.5

    return min(matches / total, 1.0)


def _compute_recency_score(year: int | None, current_year: int) -> float:
    """Exponential decay with half-life ~5 years. Minimum 0.1."""
    if year is None:
        return 0.3  # neutral score for unknown year
    age = max(current_year - year, 0)
    return max(math.exp(-_RECENCY_DECAY * age), 0.1)


def _compute_citation_score(citation_count: int) -> float:
    """Log-scaled citation score, normalized to [0, 1]."""
    if citation_count <= 0:
        return 0.0
    return min(
        math.log10(citation_count + 1) / math.log10(_MAX_EXPECTED_CITATIONS + 1),
        1.0,
    )


def _compute_abstract_match(paper: Paper, document: TexDocument) -> float:
    """Fuzzy match of paper abstract against document text."""
    if not paper.abstract or not document.full_text:
        return 0.0
    # Use partial ratio on truncated texts to avoid slowness
    paper_text = paper.abstract[:500].lower()
    doc_text = document.full_text[:2000].lower()
    return fuzz.partial_ratio(paper_text, doc_text) / 100.0


# ---------------------------------------------------------------------------
# Cite key generation
# ---------------------------------------------------------------------------

def _make_unique_cite_key(paper: Paper, existing_keys: set[str]) -> str:
    """Generate a unique BibTeX cite key: lastname + year + first title word.

    Appends a/b/c suffix on collision.
    """
    last_name = _extract_last_name(paper)
    year = str(paper.year) if paper.year else "nd"
    title_word = _first_alpha_word(paper.title or "")

    base_key = _to_ascii(f"{last_name}{year}{title_word}")
    if not base_key:
        base_key = "unknown"

    key = base_key
    suffix_idx = 0
    while key in existing_keys:
        suffix_idx += 1
        key = f"{base_key}{chr(96 + suffix_idx)}"  # a, b, c, ...

    return key


def _extract_last_name(paper: Paper) -> str:
    """Extract the first author's last name."""
    if not paper.authors:
        return "unknown"
    author = paper.authors[0]
    name = getattr(author, "family_name", "") or ""
    if not name:
        # Fall back to full name, take last word
        full = getattr(author, "name", "") or ""
        parts = full.strip().split()
        name = parts[-1] if parts else "unknown"
    return name.lower()


def _first_alpha_word(title: str) -> str:
    """Extract the first alphabetic word from a title (skip articles)."""
    skip = {"a", "an", "the", "on", "of", "in", "for", "and", "to", "with"}
    for word in re.findall(r"[a-zA-Z]+", title):
        if word.lower() not in skip:
            return word.lower()
    return ""


def _to_ascii(text: str) -> str:
    """Convert text to ASCII-safe identifier."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]", "", ascii_text)
