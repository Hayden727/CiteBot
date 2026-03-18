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
    """Parsed representation of a single LaTeX file."""

    file_path: str
    title: str
    abstract: str
    sections: tuple[tuple[str, str], ...]  # (heading, body)
    full_text: str
    existing_cite_keys: frozenset[str]
    existing_bib_file: str  # path from \\bibliography{}, or ""


@dataclass(frozen=True)
class TexProject:
    """Parsed representation of a multi-file LaTeX project.

    The main_doc is the root .tex file (containing \\input/\\include).
    child_docs are the resolved included files, in order.
    """

    main_doc: TexDocument
    child_docs: tuple[TexDocument, ...]  # empty for single-file projects
    combined_title: str
    combined_abstract: str
    combined_full_text: str
    all_existing_cite_keys: frozenset[str]
    bib_file: str

    @property
    def all_docs(self) -> tuple[TexDocument, ...]:
        return (self.main_doc,) + self.child_docs

    @property
    def is_multi_file(self) -> bool:
        return len(self.child_docs) > 0


@dataclass(frozen=True)
class ExtractedKeywords:
    """Result of keyword extraction."""

    keywords: tuple[tuple[str, float], ...]  # (keyword, score) desc by score
    source_method: str  # "llm", "ensemble", "keybert", "yake", "spacy"


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

    project: TexProject
    keywords: ExtractedKeywords
    papers: tuple[ScoredPaper, ...]
    bibtex_content: str
    output_path: str
    inserted_cites: bool
