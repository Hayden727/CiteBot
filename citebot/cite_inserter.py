"""Optional module to insert \\cite{} commands into LaTeX documents."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from rapidfuzz import fuzz

from citebot.types import ScoredPaper, TexDocument

logger = logging.getLogger(__name__)

# Minimum confidence to insert a citation
_MATCH_THRESHOLD = 0.7


def insert_citations(
    document: TexDocument,
    scored_papers: tuple[ScoredPaper, ...],
    bib_filename: str = "references",
) -> str:
    """Insert \\cite{} references into the .tex source.

    Returns the modified .tex content as a new string (immutable).
    Does NOT write to disk — caller decides.
    """
    tex_content = Path(document.file_path).read_text(encoding="utf-8")

    # Find citation insertion points
    insertions = _find_citation_points(tex_content, scored_papers, document)

    if insertions:
        tex_content = _insert_at_positions(tex_content, insertions)
        logger.info("Inserted %d citation(s) into document", len(insertions))
    else:
        logger.info("No suitable citation points found")

    tex_content = _ensure_bibliography_command(tex_content, bib_filename)
    return tex_content


def write_modified_tex(content: str, original_path: str) -> str:
    """Write modified .tex to a .cited.tex file (never overwrites original).

    Returns the path written.
    """
    original = Path(original_path)
    output_path = original.with_suffix(".cited.tex")
    output_path.write_text(content, encoding="utf-8")
    logger.info("Wrote modified .tex to %s", output_path)
    return str(output_path)


# ---------------------------------------------------------------------------
# Finding citation points
# ---------------------------------------------------------------------------

def _find_citation_points(
    tex_content: str,
    papers: tuple[ScoredPaper, ...],
    document: TexDocument,
) -> list[tuple[int, list[str]]]:
    """Find positions where citations should be inserted.

    Returns list of (position, [cite_keys]) sorted by position descending.
    """
    # Find section boundaries in the raw tex
    section_pattern = r"\\section\{[^}]*\}"
    section_matches = list(re.finditer(section_pattern, tex_content))

    if not section_matches:
        return []

    # For each section, find the best matching papers
    insertion_map: dict[int, list[str]] = {}

    for i, sec_match in enumerate(section_matches):
        sec_start = sec_match.end()
        sec_end = (
            section_matches[i + 1].start()
            if i + 1 < len(section_matches)
            else len(tex_content)
        )
        section_text = tex_content[sec_start:sec_end]
        heading = sec_match.group()

        # Find sentences in this section that end with a period
        sentence_ends = _find_sentence_ends(section_text, sec_start)

        for sent_pos, sentence in sentence_ends:
            matching_keys = _match_papers_to_sentence(sentence, papers)
            if matching_keys:
                insertion_map[sent_pos] = matching_keys

    # Convert to sorted list (descending position so insertions don't shift)
    result = sorted(insertion_map.items(), key=lambda x: x[0], reverse=True)
    return result


def _find_sentence_ends(
    section_text: str, offset: int
) -> list[tuple[int, str]]:
    """Find positions of sentence-ending periods in section text.

    Returns list of (absolute_position, sentence_text).
    Only includes sentences outside LaTeX commands.
    """
    results: list[tuple[int, str]] = []

    # Split into sentences roughly at ". " or ".\n"
    sentence_pattern = r"[^.]+\."
    for m in re.finditer(sentence_pattern, section_text):
        sentence = m.group().strip()
        # Skip sentences that are inside commands or very short
        if len(sentence) < 20:
            continue
        if re.match(r"^\s*\\", sentence):
            continue

        end_pos = offset + m.end()
        results.append((end_pos, sentence))

    return results


def _match_papers_to_sentence(
    sentence: str,
    papers: tuple[ScoredPaper, ...],
) -> list[str]:
    """Find papers that match a sentence above the confidence threshold."""
    matched_keys: list[str] = []
    sentence_lower = sentence.lower()

    for sp in papers:
        score = _match_paper_to_sentence(sentence_lower, sp)
        if score >= _MATCH_THRESHOLD:
            matched_keys.append(sp.cite_key)

    # Limit to 3 citations per insertion point
    return matched_keys[:3]


def _match_paper_to_sentence(sentence: str, paper: ScoredPaper) -> float:
    """Score how well a paper matches a sentence (0-1)."""
    scores: list[float] = []

    # Check title words in sentence
    if paper.paper.title:
        title_words = set(paper.paper.title.lower().split()) - {
            "a", "an", "the", "of", "in", "for", "and", "to", "with", "on",
        }
        if title_words:
            overlap = sum(1 for w in title_words if w in sentence)
            scores.append(overlap / len(title_words))

    # Check paper keywords
    paper_kws = getattr(paper.paper, "keywords", None) or []
    for kw in paper_kws[:5]:
        if isinstance(kw, str) and kw.lower() in sentence:
            scores.append(0.8)
            break

    # Partial ratio of abstract vs sentence
    if paper.paper.abstract:
        ratio = fuzz.partial_ratio(
            sentence[:200], paper.paper.abstract[:200].lower()
        ) / 100.0
        scores.append(ratio * 0.5)

    return max(scores) if scores else 0.0


# ---------------------------------------------------------------------------
# Insertion helpers
# ---------------------------------------------------------------------------

def _insert_at_positions(
    tex_content: str,
    insertions: list[tuple[int, list[str]]],
) -> str:
    """Insert \\cite{key1,key2} at the given positions.

    Insertions must be sorted by position descending.
    """
    result = tex_content
    for pos, keys in insertions:
        cite_cmd = "~\\cite{" + ",".join(keys) + "}"
        # Insert before the period at position pos
        # pos points to just after the period, so insert before it
        insert_pos = pos - 1
        if 0 <= insert_pos < len(result) and result[insert_pos] == ".":
            result = result[:insert_pos] + cite_cmd + result[insert_pos:]
        else:
            result = result[:pos] + cite_cmd + result[pos:]

    return result


def _ensure_bibliography_command(
    tex_content: str,
    bib_filename: str,
) -> str:
    """Add \\bibliography{filename} before \\end{document} if not present."""
    if re.search(r"\\bibliography\{", tex_content):
        return tex_content
    if re.search(r"\\addbibresource\{", tex_content):
        return tex_content

    end_doc = tex_content.rfind(r"\end{document}")
    if end_doc == -1:
        return tex_content

    bib_block = (
        f"\n\\bibliographystyle{{plain}}\n"
        f"\\bibliography{{{bib_filename}}}\n\n"
    )
    return tex_content[:end_doc] + bib_block + tex_content[end_doc:]
