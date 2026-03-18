"""Immutable data types and exceptions for CiteBot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from opencite.models import Paper


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class CiteBotError(Exception):
    """Base exception for CiteBot."""


class TexParseError(CiteBotError):
    """Failed to parse a .tex file."""


class KeywordExtractionError(CiteBotError):
    """Failed to extract keywords from document text."""


class SearchError(CiteBotError):
    """Literature search failed or returned no results."""


# ---------------------------------------------------------------------------
# Data structures (all frozen / immutable)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TexDocument:
    """Parsed representation of a LaTeX document."""

    file_path: str
    title: str
    abstract: str
    sections: tuple[tuple[str, str], ...]  # (heading, body)
    full_text: str
    existing_cite_keys: frozenset[str]
    existing_bib_file: str  # path from \\bibliography{}, or ""


@dataclass(frozen=True)
class ExtractedKeywords:
    """Result of keyword extraction."""

    keywords: tuple[tuple[str, float], ...]  # (keyword, score) desc by score
    source_method: str  # "ensemble", "keybert", "yake", "spacy"


@dataclass(frozen=True)
class ScoredPaper:
    """A paper annotated with relevance scores and a BibTeX cite key."""

    paper: "Paper"
    relevance_score: float
    keyword_overlap: float
    recency_score: float
    citation_score: float
    cite_key: str


@dataclass(frozen=True)
class PipelineResult:
    """Immutable result of the full CiteBot pipeline."""

    document: TexDocument
    keywords: ExtractedKeywords
    papers: tuple[ScoredPaper, ...]
    bibtex_content: str
    output_path: str
    inserted_cites: bool
