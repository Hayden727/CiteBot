"""Parse LaTeX files into structured TexDocument / TexProject objects."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from citebot.types import TexDocument, TexParseError, TexProject

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_tex_file(file_path: str) -> TexDocument:
    """Read and parse a single .tex file into a TexDocument.

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


def parse_tex_project(main_path: str) -> TexProject:
    """Parse a multi-file LaTeX project starting from the main .tex file.

    Recursively resolves \\input{} and \\include{} directives.
    Returns a TexProject containing the main document and all children.
    """
    main_file = Path(main_path).resolve()
    _validate_path(main_file)

    raw = _read_file(main_file)
    cleaned = _strip_comments(raw)

    # Resolve child files
    child_paths = _resolve_includes(cleaned, main_file.parent)
    logger.info(
        "Found %d included files in %s: %s",
        len(child_paths),
        main_path,
        [p.name for p in child_paths],
    )

    # Parse main doc
    main_doc = parse_tex_file(str(main_file))

    # Parse each child
    child_docs: list[TexDocument] = []
    for child_path in child_paths:
        try:
            child_doc = parse_tex_file(str(child_path))
            child_docs.append(child_doc)
            logger.info("Parsed child: %s (%d sections)", child_path.name, len(child_doc.sections))
        except TexParseError as exc:
            logger.warning("Skipping %s: %s", child_path.name, exc)

    # Combine
    all_docs = [main_doc] + child_docs
    combined_title = main_doc.title
    combined_abstract = main_doc.abstract

    # Prefer title from main doc; if empty, try children
    if not combined_title:
        for doc in child_docs:
            if doc.title:
                combined_title = doc.title
                break

    combined_text = "\n\n".join(doc.full_text for doc in all_docs if doc.full_text)
    all_cites = frozenset().union(*(doc.existing_cite_keys for doc in all_docs))
    bib_file = main_doc.existing_bib_file
    if not bib_file:
        for doc in child_docs:
            if doc.existing_bib_file:
                bib_file = doc.existing_bib_file
                break

    project = TexProject(
        main_doc=main_doc,
        child_docs=tuple(child_docs),
        combined_title=combined_title,
        combined_abstract=combined_abstract,
        combined_full_text=combined_text,
        all_existing_cite_keys=all_cites,
        bib_file=bib_file,
    )
    logger.info(
        "Project parsed: %d files, %d total sections, %d existing cites",
        len(all_docs),
        sum(len(d.sections) for d in all_docs),
        len(all_cites),
    )
    return project


# ---------------------------------------------------------------------------
# Include resolution
# ---------------------------------------------------------------------------

def _resolve_includes(tex: str, base_dir: Path) -> list[Path]:
    """Find and resolve \\input{} and \\include{} to file paths.

    Searches relative to base_dir. Appends .tex if missing.
    Returns paths in document order, skipping missing files.
    """
    pattern = r"\\(?:input|include)\{([^}]+)\}"
    paths: list[Path] = []
    seen: set[str] = set()

    for m in re.finditer(pattern, tex):
        ref = m.group(1).strip()
        if ref in seen:
            continue
        seen.add(ref)

        resolved = _find_tex_file(ref, base_dir)
        if resolved is not None:
            paths.append(resolved)
            # Recurse into child for nested includes
            try:
                child_raw = _read_file(resolved)
                child_cleaned = _strip_comments(child_raw)
                nested = _resolve_includes(child_cleaned, resolved.parent)
                for np in nested:
                    if np not in paths:
                        paths.append(np)
            except TexParseError:
                pass
        else:
            logger.warning("Included file not found: %s (base: %s)", ref, base_dir)

    return paths


def _find_tex_file(ref: str, base_dir: Path) -> Path | None:
    """Resolve a LaTeX include reference to an actual file path."""
    # Try as-is first
    candidate = base_dir / ref
    if candidate.is_file():
        return candidate.resolve()

    # Try with .tex extension
    candidate_tex = base_dir / (ref + ".tex")
    if candidate_tex.is_file():
        return candidate_tex.resolve()

    # Try in common subdirectories
    for subdir in ("chapters", "sections", "content", "tex"):
        for suffix in ("", ".tex"):
            candidate = base_dir / subdir / (ref + suffix)
            if candidate.is_file():
                return candidate.resolve()

    return None


# ---------------------------------------------------------------------------
# Internal helpers (unchanged)
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
    r"""Extract content of \title{...} or \chapter{...}, handling nested braces."""
    title = _extract_braced_arg(tex, r"\\title")
    if not title:
        title = _extract_braced_arg(tex, r"\\chapter")
    return title


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
    """Extract the first brace-delimited argument of a LaTeX command."""
    m = re.search(command_pattern + r"\s*\{", tex)
    if not m:
        return ""

    start = m.end()
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
    for env in ("figure", "table", "tabular", "lstlisting", "equation", "align", "tikzpicture"):
        text = re.sub(
            rf"\\begin\{{{env}\}}.*?\\end\{{{env}\}}",
            " ",
            text,
            flags=re.DOTALL,
        )
    text = re.sub(r"\\(?:label|ref|cref|eqref|autoref|pageref)\{[^}]*\}", " ", text)
    text = re.sub(r"\\cite[pt]?\{[^}]*\}", " ", text)
    text = re.sub(r"\\includegraphics\[[^\]]*\]\{[^}]*\}", " ", text)
    text = re.sub(r"\\(?:begin|end)\{[^}]*\}", "", text)
    text = re.sub(r"\\\[.*?\\\]", " ", text, flags=re.DOTALL)
    text = re.sub(r"\$\$.*?\$\$", " ", text, flags=re.DOTALL)
    text = re.sub(r"\$[^$]+\$", " ", text)
    text = re.sub(r"\\cde\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?\s*", " ", text)
    text = text.replace("{", "").replace("}", "")
    text = re.sub(r"~", " ", text)
    text = re.sub(r"\\\\", " ", text)
    text = re.sub(r"&", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
