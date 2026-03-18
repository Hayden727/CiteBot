"""Tests for multi-file LaTeX project support."""

import pytest
from pathlib import Path

from citebot.latex_parser import parse_tex_project, _resolve_includes, _find_tex_file
from citebot.types import TexProject


@pytest.fixture
def multi_file_project(tmp_path):
    """Create a multi-file LaTeX project in tmp_path."""
    main = tmp_path / "main.tex"
    main.write_text(r"""
\documentclass{article}
\title{My Thesis}
\begin{document}
\maketitle
\begin{abstract}
This thesis studies deep learning.
\end{abstract}
\input{chap01}
\input{chap02}
\bibliography{references}
\end{document}
""")

    chap01 = tmp_path / "chap01.tex"
    chap01.write_text(r"""
\chapter{Introduction}
\section{Background}
Deep learning has revolutionized machine learning and artificial intelligence.
Neural networks can learn complex representations from data.
\section{Motivation}
We aim to improve training efficiency of large language models.
""")

    chap02 = tmp_path / "chap02.tex"
    chap02.write_text(r"""
\chapter{Methods}
\section{Architecture}
We propose a transformer-based architecture with sparse attention mechanisms.
\section{Training}
The model is trained using distributed data parallelism across multiple GPUs.
""")

    return tmp_path, str(main)


class TestParseTexProject:
    def test_parses_multi_file(self, multi_file_project):
        tmp_path, main_path = multi_file_project
        project = parse_tex_project(main_path)

        assert isinstance(project, TexProject)
        assert project.is_multi_file
        assert len(project.child_docs) == 2
        assert len(project.all_docs) == 3

    def test_combined_title(self, multi_file_project):
        _, main_path = multi_file_project
        project = parse_tex_project(main_path)
        assert "My Thesis" in project.combined_title

    def test_combined_text_includes_all_chapters(self, multi_file_project):
        _, main_path = multi_file_project
        project = parse_tex_project(main_path)
        assert "deep learning" in project.combined_full_text.lower()
        assert "transformer" in project.combined_full_text.lower()
        assert "distributed data" in project.combined_full_text.lower()

    def test_collects_all_cite_keys(self, tmp_path):
        main = tmp_path / "main2.tex"
        main.write_text(r"""
\documentclass{article}
\title{Test}
\begin{document}
See \cite{smith2020}.
\input{child}
\end{document}
""")
        child = tmp_path / "child.tex"
        child.write_text(r"""
\section{Related Work}
Prior work \cite{doe2021} shows progress.
""")

        project = parse_tex_project(str(main))
        assert "smith2020" in project.all_existing_cite_keys
        assert "doe2021" in project.all_existing_cite_keys

    def test_bib_file_from_main(self, multi_file_project):
        _, main_path = multi_file_project
        project = parse_tex_project(main_path)
        assert project.bib_file == "references"

    def test_single_file_project(self, sample_tex_path):
        project = parse_tex_project(sample_tex_path)
        assert not project.is_multi_file
        assert len(project.child_docs) == 0
        assert len(project.all_docs) == 1


class TestResolveIncludes:
    def test_finds_tex_files(self, tmp_path):
        (tmp_path / "chap01.tex").write_text("content")
        (tmp_path / "chap02.tex").write_text("content")
        tex = r"\input{chap01}\include{chap02}"
        paths = _resolve_includes(tex, tmp_path)
        names = [p.name for p in paths]
        assert "chap01.tex" in names
        assert "chap02.tex" in names

    def test_skips_missing_files(self, tmp_path):
        tex = r"\input{nonexistent}"
        paths = _resolve_includes(tex, tmp_path)
        assert len(paths) == 0

    def test_appends_tex_extension(self, tmp_path):
        (tmp_path / "chapter.tex").write_text("content")
        tex = r"\input{chapter}"
        paths = _resolve_includes(tex, tmp_path)
        assert len(paths) == 1
        assert paths[0].name == "chapter.tex"


class TestFindTexFile:
    def test_finds_with_extension(self, tmp_path):
        (tmp_path / "file.tex").write_text("")
        assert _find_tex_file("file.tex", tmp_path) is not None

    def test_finds_without_extension(self, tmp_path):
        (tmp_path / "file.tex").write_text("")
        assert _find_tex_file("file", tmp_path) is not None

    def test_finds_in_subdirectory(self, tmp_path):
        chapters_dir = tmp_path / "chapters"
        chapters_dir.mkdir()
        (chapters_dir / "intro.tex").write_text("")
        assert _find_tex_file("intro", tmp_path) is not None

    def test_returns_none_for_missing(self, tmp_path):
        assert _find_tex_file("missing", tmp_path) is None
