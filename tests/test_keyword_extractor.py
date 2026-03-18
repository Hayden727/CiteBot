"""Tests for the keyword extractor module."""

from unittest.mock import MagicMock, patch

import pytest

from citebot.keyword_extractor import (
    _build_weighted_text,
    _ensemble_merge,
    _normalize_yake_scores,
    extract_keywords,
)
from citebot.types import ExtractedKeywords, KeywordExtractionError, TexDocument


@pytest.fixture
def minimal_document():
    return TexDocument(
        file_path="/test/paper.tex",
        title="Deep Learning for Protein Folding",
        abstract="Neural networks predict protein structures from sequences.",
        sections=(
            ("Methods", "Transformer architectures process amino acid sequences."),
        ),
        full_text="Deep Learning for Protein Folding. Neural networks predict protein structures.",
        existing_cite_keys=frozenset(),
        existing_bib_file="",
    )


class TestBuildWeightedText:
    def test_title_repeated_3x(self, minimal_document):
        text = _build_weighted_text(minimal_document)
        title = minimal_document.title
        assert text.count(title) == 3

    def test_abstract_repeated_2x(self, minimal_document):
        text = _build_weighted_text(minimal_document)
        abstract = minimal_document.abstract
        assert text.count(abstract) == 2

    def test_includes_section_text(self, minimal_document):
        text = _build_weighted_text(minimal_document)
        assert "Transformer" in text


class TestNormalizeYakeScores:
    def test_inverts_scores(self):
        raw = [("word1", 0.1), ("word2", 0.5), ("word3", 1.0)]
        result = _normalize_yake_scores(raw)
        # Lower YAKE score = better, so word1 should have highest normalized score
        scores = {kw: s for kw, s in result}
        assert scores["word1"] > scores["word3"]

    def test_empty_input(self):
        assert _normalize_yake_scores([]) == []


class TestEnsembleMerge:
    def test_merges_and_deduplicates(self):
        keybert = [("deep learning", 0.9), ("protein", 0.8)]
        yake = [("Deep Learning", 0.7), ("structure", 0.6)]
        spacy = [("protein", 0.5), ("neural network", 0.4)]

        result = _ensemble_merge(keybert, yake, spacy, top_n=5)
        keywords = [kw for kw, _ in result]

        # "deep learning" should appear once (deduped)
        assert keywords.count("deep learning") == 1
        # "protein" should appear once (deduped)
        assert keywords.count("protein") == 1
        # All unique keywords present
        assert len(result) == 4

    def test_respects_top_n(self):
        kw = [(f"word{i}", 1.0 - i * 0.1) for i in range(10)]
        result = _ensemble_merge(kw, [], [], top_n=3)
        assert len(result) == 3

    def test_weighted_scoring(self):
        # KeyBERT weight is highest (0.5), so its top keyword should dominate
        keybert = [("keybert_top", 1.0)]
        yake = [("yake_top", 1.0)]
        spacy = [("spacy_top", 1.0)]

        result = _ensemble_merge(keybert, yake, spacy, top_n=3)
        scores = {kw: s for kw, s in result}
        assert scores["keybert_top"] > scores["spacy_top"]


class TestExtractKeywords:
    def test_raises_on_empty_text(self):
        empty_doc = TexDocument(
            file_path="/test/empty.tex",
            title="",
            abstract="",
            sections=(),
            full_text="",
            existing_cite_keys=frozenset(),
            existing_bib_file="",
        )
        with pytest.raises(KeywordExtractionError, match="No text"):
            extract_keywords(empty_doc)

    @patch("citebot.keyword_extractor._extract_keybert")
    @patch("citebot.keyword_extractor._extract_yake")
    @patch("citebot.keyword_extractor._extract_spacy_noun_phrases")
    def test_falls_back_when_extractors_fail(
        self, mock_spacy, mock_yake, mock_keybert, minimal_document
    ):
        mock_keybert.side_effect = RuntimeError("model not found")
        mock_yake.return_value = [("protein", 0.8), ("deep learning", 0.7)]
        mock_spacy.side_effect = RuntimeError("model not found")

        result = extract_keywords(minimal_document, top_n=5)
        assert result.source_method == "yake"
        assert len(result.keywords) > 0

    @patch("citebot.keyword_extractor._extract_keybert")
    @patch("citebot.keyword_extractor._extract_yake")
    @patch("citebot.keyword_extractor._extract_spacy_noun_phrases")
    def test_raises_when_all_fail(
        self, mock_spacy, mock_yake, mock_keybert, minimal_document
    ):
        mock_keybert.side_effect = RuntimeError("fail")
        mock_yake.side_effect = RuntimeError("fail")
        mock_spacy.side_effect = RuntimeError("fail")

        with pytest.raises(KeywordExtractionError, match="All keyword extractors"):
            extract_keywords(minimal_document)

    @patch("citebot.keyword_extractor._extract_keybert")
    @patch("citebot.keyword_extractor._extract_yake")
    @patch("citebot.keyword_extractor._extract_spacy_noun_phrases")
    def test_ensemble_merge_called(
        self, mock_spacy, mock_yake, mock_keybert, minimal_document
    ):
        mock_keybert.return_value = [("deep learning", 0.9)]
        mock_yake.return_value = [("protein", 0.8)]
        mock_spacy.return_value = [("neural network", 0.7)]

        result = extract_keywords(minimal_document, top_n=5)
        assert result.source_method == "ensemble"
        assert len(result.keywords) == 3
