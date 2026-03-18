"""Tests for the LaTeX parser module."""

import pytest

from citebot.latex_parser import (
    _extract_abstract,
    _extract_bibliography_path,
    _extract_braced_arg,
    _extract_existing_cites,
    _extract_sections,
    _extract_title,
    _strip_comments,
    _strip_latex_commands,
    parse_tex_file,
)
from citebot.types import TexParseError


class TestParseTexFile:
    def test_parses_sample_tex(self, sample_tex_path):
        doc = parse_tex_file(sample_tex_path)
        assert "Protein Structure Prediction" in doc.title
        assert "deep learning" in doc.abstract.lower()
        assert len(doc.sections) == 4
        assert doc.existing_bib_file == "references"

    def test_extracts_section_headings(self, sample_tex_path):
        doc = parse_tex_file(sample_tex_path)
        headings = [h for h, _ in doc.sections]
        assert "Introduction" in headings
        assert "Methods" in headings
        assert "Results" in headings
        assert "Conclusion" in headings

    def test_full_text_not_empty(self, sample_tex_path):
        doc = parse_tex_file(sample_tex_path)
        assert len(doc.full_text) > 100

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(TexParseError, match="not found"):
            parse_tex_file(str(tmp_path / "nonexistent.tex"))

    def test_non_tex_file_raises(self, tmp_path):
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("hello")
        with pytest.raises(TexParseError, match=".tex"):
            parse_tex_file(str(txt_file))

    def test_empty_tex_raises(self, tmp_path):
        tex = tmp_path / "empty.tex"
        tex.write_text("\\documentclass{article}\n\\begin{document}\n\\end{document}")
        with pytest.raises(TexParseError, match="No extractable text"):
            parse_tex_file(str(tex))


class TestStripComments:
    def test_removes_line_comments(self):
        assert _strip_comments("hello % comment\nworld") == "hello \nworld"

    def test_preserves_escaped_percent(self):
        assert "\\%" in _strip_comments("100\\% accurate")


class TestExtractTitle:
    def test_extracts_simple_title(self):
        tex = "\\title{My Paper Title}"
        assert _extract_title(tex) == "My Paper Title"

    def test_extracts_nested_braces(self):
        tex = "\\title{A {Deep} Learning Paper}"
        assert _extract_title(tex) == "A {Deep} Learning Paper"

    def test_returns_empty_when_missing(self):
        assert _extract_title("no title here") == ""


class TestExtractAbstract:
    def test_extracts_abstract(self):
        tex = "\\begin{abstract}Some abstract text.\\end{abstract}"
        assert _extract_abstract(tex) == "Some abstract text."

    def test_returns_empty_when_missing(self):
        assert _extract_abstract("no abstract") == ""


class TestExtractSections:
    def test_extracts_sections(self):
        tex = "\\section{Intro}Text here.\\section{Methods}More text."
        sections = _extract_sections(tex)
        assert len(sections) == 2
        assert sections[0][0] == "Intro"
        assert "Text here" in sections[0][1]

    def test_returns_empty_for_no_sections(self):
        assert _extract_sections("just text") == ()


class TestExtractExistingCites:
    def test_finds_cite(self):
        cites = _extract_existing_cites("\\cite{smith2020}")
        assert "smith2020" in cites

    def test_finds_citep(self):
        cites = _extract_existing_cites("\\citep{doe2021,lee2022}")
        assert "doe2021" in cites
        assert "lee2022" in cites

    def test_returns_empty_for_no_cites(self):
        assert _extract_existing_cites("no cites") == frozenset()


class TestExtractBibliographyPath:
    def test_finds_bibliography(self):
        assert _extract_bibliography_path("\\bibliography{refs}") == "refs"

    def test_finds_addbibresource(self):
        path = _extract_bibliography_path("\\addbibresource{my_refs.bib}")
        assert path == "my_refs.bib"

    def test_returns_empty_when_missing(self):
        assert _extract_bibliography_path("no bib") == ""


class TestStripLatexCommands:
    def test_removes_commands_keeps_text(self):
        result = _strip_latex_commands("\\textbf{bold} and \\emph{italic}")
        assert "bold" in result
        assert "italic" in result
        assert "\\" not in result

    def test_removes_math_mode(self):
        result = _strip_latex_commands("some $x^2$ math")
        assert "x^2" not in result
        assert "some" in result

    def test_removes_environments(self):
        result = _strip_latex_commands("\\begin{figure}content\\end{figure}")
        assert "\\begin" not in result
