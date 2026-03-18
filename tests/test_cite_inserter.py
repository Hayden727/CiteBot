"""Tests for the citation inserter module."""

import pytest

from citebot.cite_inserter import (
    _ensure_bibliography_command,
    _match_paper_to_sentence,
    insert_citations,
)
from citebot.types import ScoredPaper


class TestEnsureBibliographyCommand:
    def test_adds_bibliography_when_missing(self):
        tex = "\\begin{document}\nHello.\n\\end{document}"
        result = _ensure_bibliography_command(tex, "refs")
        assert "\\bibliography{refs}" in result

    def test_does_not_duplicate(self):
        tex = "\\bibliography{existing}\n\\end{document}"
        result = _ensure_bibliography_command(tex, "refs")
        assert result.count("\\bibliography") == 1

    def test_handles_addbibresource(self):
        tex = "\\addbibresource{refs.bib}\n\\end{document}"
        result = _ensure_bibliography_command(tex, "refs")
        assert "\\bibliography" not in result


class TestMatchPaperToSentence:
    def test_high_match_with_title_words(self, mock_paper):
        sp = ScoredPaper(
            paper=mock_paper,
            relevance_score=0.9,
            keyword_overlap=0.8,
            recency_score=0.9,
            citation_score=0.7,
            cite_key="smith2023deep",
        )
        sentence = "deep learning methods are used for protein structure prediction tasks"
        score = _match_paper_to_sentence(sentence, sp)
        assert score > 0.5

    def test_low_match_unrelated(self, mock_paper):
        sp = ScoredPaper(
            paper=mock_paper,
            relevance_score=0.9,
            keyword_overlap=0.8,
            recency_score=0.9,
            citation_score=0.7,
            cite_key="smith2023deep",
        )
        sentence = "the weather forecast predicts rain tomorrow in the city"
        score = _match_paper_to_sentence(sentence, sp)
        assert score < 0.5
