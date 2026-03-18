"""Parse LaTeX files into structured TexDocument objects."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from citebot.types import TexDocument, TexParseError

logger = logging.getLogger(__name__)


def parse_tex_file(file_path: str) -> TexDocument:
    """Read and parse a .tex file into a TexDocument.

    Raises:
        TexParseError: If the file cannot be read or parsed.
    """
    path = Path(file_path)
    _validate_path(path)

    raw = _read_file(path)
    cleaned = _strip_comments(raw)

    title = _extract_title(cleaned)
    abstract = _extract_abstract(cleaned)
    sections = _extract_sections(cleaned)
    existing_cites = _extract_existing_cites(cleaned)
    bib_file = _extract_bibliography_path(cleaned)

    plain_parts: list[str] = []
    if title:
        plain_parts.append(_strip_latex_commands(title))
    if abstract:
        plain_parts.append(_strip_latex_commands(abstract))
    for _heading, body in sections:
        plain_parts.append(_strip_latex_commands(body))

    full_text = "\n\n".join(plain_parts).strip()

    if not full_text:
        raise TexParseError(f"No extractable text found in {file_path}")

    doc = TexDocument(
        file_path=str(path.resolve()),
        title=_strip_latex_commands(title),
        abstract=_strip_latex_commands(abstract),
        sections=tuple(
            (_strip_latex_commands(h), _strip_latex_commands(b))
            for h, b in sections
        ),
        full_text=full_text,
        existing_cite_keys=existing_cites,
        existing_bib_file=bib_file,
    )
    logger.info(
        "Parsed %s: title=%r, %d sections, %d existing cites",
        file_path,
        doc.title[:60],
        len(doc.sections),
        len(doc.existing_cite_keys),
    )
    return doc


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_path(path: Path) -> None:
    if not path.exists():
        raise TexParseError(f"File not found: {path}")
    if not path.is_file():
        raise TexParseError(f"Not a file: {path}")
    if path.suffix.lower() != ".tex":
        raise TexParseError(f"Expected a .tex file, got: {path.suffix}")


def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="latin-1")
        except Exception as exc:
            raise TexParseError(f"Cannot decode {path}: {exc}") from exc
    except OSError as exc:
        raise TexParseError(f"Cannot read {path}: {exc}") from exc


def _strip_comments(tex: str) -> str:
    """Remove LaTeX comments (% to end-of-line), preserving escaped \\%."""
    return re.sub(r"(?<!\\)%.*", "", tex)


def _extract_title(tex: str) -> str:
    r"""Extract content of \title{...}, handling nested braces."""
    return _extract_braced_arg(tex, r"\\title")


def _extract_abstract(tex: str) -> str:
    r"""Extract text between \begin{abstract} and \end{abstract}."""
    m = re.search(
        r"\\begin\{abstract\}(.*?)\\end\{abstract\}",
        tex,
        re.DOTALL,
    )
    return m.group(1).strip() if m else ""


def _extract_sections(tex: str) -> tuple[tuple[str, str], ...]:
    r"""Extract (heading, body) pairs for each \section{...}."""
    pattern = r"\\section\{([^}]*)\}"
    matches = list(re.finditer(pattern, tex))
    if not matches:
        return ()

    sections: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(tex)
        body = tex[start:end].strip()
        # Stop body at document-level commands
        for stop_cmd in (r"\bibliography", r"\end{document}", r"\appendix"):
            idx = body.find(stop_cmd)
            if idx != -1:
                body = body[:idx].strip()
        sections.append((heading, body))

    return tuple(sections)


def _extract_existing_cites(tex: str) -> frozenset[str]:
    r"""Find all cite keys from \cite{}, \citep{}, \citet{}, \citeauthor{}, etc."""
    keys: set[str] = set()
    for m in re.finditer(r"\\cite[pt]?\{([^}]+)\}", tex):
        for key in m.group(1).split(","):
            stripped = key.strip()
            if stripped:
                keys.add(stripped)
    return frozenset(keys)


def _extract_bibliography_path(tex: str) -> str:
    r"""Find the bibliography file from \bibliography{} or \addbibresource{}."""
    for pattern in (r"\\bibliography\{([^}]+)\}", r"\\addbibresource\{([^}]+)\}"):
        m = re.search(pattern, tex)
        if m:
            return m.group(1).strip()
    return ""


def _extract_braced_arg(tex: str, command_pattern: str) -> str:
    """Extract the first brace-delimited argument of a LaTeX command.

    Handles one level of nested braces.
    """
    m = re.search(command_pattern + r"\s*\{", tex)
    if not m:
        return ""

    start = m.end()  # position right after the opening {
    depth = 1
    i = start
    while i < len(tex) and depth > 0:
        if tex[i] == "{" and (i == 0 or tex[i - 1] != "\\"):
            depth += 1
        elif tex[i] == "}" and (i == 0 or tex[i - 1] != "\\"):
            depth -= 1
        i += 1

    return tex[start : i - 1].strip() if depth == 0 else ""


def _strip_latex_commands(tex: str) -> str:
    """Remove LaTeX commands and markup, keeping plain text."""
    text = tex
    # Remove environments (begin/end)
    text = re.sub(r"\\(?:begin|end)\{[^}]*\}", "", text)
    # Remove display math
    text = re.sub(r"\\\[.*?\\\]", " ", text, flags=re.DOTALL)
    text = re.sub(r"\$\$.*?\$\$", " ", text, flags=re.DOTALL)
    # Remove inline math
    text = re.sub(r"\$[^$]+\$", " ", text)
    # Remove commands with braced args (keep the arg text): \textbf{word} -> word
    text = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", text)
    # Remove commands without args: \maketitle, \noindent, etc.
    text = re.sub(r"\\[a-zA-Z]+\*?\s*", " ", text)
    # Remove remaining braces
    text = text.replace("{", "").replace("}", "")
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()
