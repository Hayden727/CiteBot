"""Generate BibTeX content and write .bib files."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import bibtexparser
from opencite.bibtex import fetch_bibtex, generate_bibtex
from opencite.models import Paper

from citebot.types import ScoredPaper

logger = logging.getLogger(__name__)


async def generate_bibtex_content(
    scored_papers: tuple[ScoredPaper, ...],
) -> str:
    """Generate complete .bib file content from scored papers.

    For each paper, tries fetch_bibtex (DOI content negotiation) first,
    then falls back to generate_bibtex from metadata.
    """
    entries: list[str] = []

    for sp in scored_papers:
        entry = await _fetch_or_generate(sp.paper)
        if entry:
            entry = _replace_cite_key(entry, sp.cite_key)
            entries.append(entry.strip())
        else:
            logger.warning(
                "Could not generate BibTeX for: %s", sp.paper.title or "unknown"
            )

    if not entries:
        return ""

    content = "\n\n".join(entries) + "\n"
    return _validate_bibtex(content)


def write_bib_file(content: str, output_path: str) -> str:
    """Write BibTeX content to a file. Returns the absolute path written.

    Creates parent directories if needed.
    """
    path = Path(output_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    logger.info("Wrote %d bytes to %s", len(content), path)
    return str(path)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _fetch_or_generate(paper: Paper) -> str:
    """Try fetch_bibtex (network), fall back to generate_bibtex (local)."""
    try:
        result = await fetch_bibtex(paper)
        if result and result.strip():
            return result
    except Exception as exc:
        logger.debug("fetch_bibtex failed for %r: %s", paper.title, exc)

    try:
        result = generate_bibtex(paper)
        if result and result.strip():
            return result
    except Exception as exc:
        logger.debug("generate_bibtex failed for %r: %s", paper.title, exc)

    return ""


def _replace_cite_key(bibtex_entry: str, new_key: str) -> str:
    """Replace the cite key in a BibTeX entry string.

    Pattern: @type{OLD_KEY, -> @type{new_key,
    """
    return re.sub(
        r"(@\w+\{)\s*[^,]+,",
        rf"\g<1>{new_key},",
        bibtex_entry,
        count=1,
    )


def _validate_bibtex(content: str) -> str:
    """Validate BibTeX content by parsing it. Returns content if valid.

    Logs warnings for any issues but does not raise — partial output
    is better than no output.
    """
    try:
        db = bibtexparser.loads(content)
        n_entries = len(db.entries)
        logger.debug("BibTeX validation: %d entries parsed successfully", n_entries)
    except Exception as exc:
        logger.warning("BibTeX validation warning: %s", exc)

    return content
