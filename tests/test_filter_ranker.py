"""Tests for the filter and ranker module."""

import pytest

from citebot.filter_ranker import (
    _compute_citation_score,
    _compute_keyword_overlap,
    _compute_recency_score,
    _deduplicate_papers,
    _first_alpha_word,
    _is_title_duplicate,
    _make_unique_cite_key,
    _to_ascii,
    filter_and_rank,
)
from citebot.types import ExtractedKeywords, TexDocument


class TestDeduplicatePapers:
    def test_removes_doi_duplicates(self, mock_papers):
        # Add a paper with same DOI as first
        from dataclasses import dataclass

        @dataclass
        class DupIDSet:
            doi: str = "10.1234/test.2024"
            pmid: str = ""
            pmcid: str = ""
            openalex_id: str = ""
            s2_id: str = ""
            arxiv_id: str = ""

        @dataclass
        class DupPaper:
            title: str = "Same DOI Paper"
            authors: list = None
            year: int = 2023
            abstract: str = ""
            citation_count: int = 0
            ids: DupIDSet = None
            keywords: list = None
            url: str = ""
            pdf_locations: list = None
            is_oa: bool = False
            influential_citation_count: int = 0
            is_retracted: bool = False
            source_venue: object = None
            publication_date: str = ""
            pub_type: str = ""
            tldr: str = ""
            mesh_terms: list = None
            topics: list = None
            _bibtex: str = ""

            def __post_init__(self):
                if self.authors is None:
                    self.authors = []
                if self.ids is None:
                    self.ids = DupIDSet()
                if self.keywords is None:
                    self.keywords = []
                if self.pdf_locations is None:
                    self.pdf_locations = []
                if self.mesh_terms is None:
                    self.mesh_terms = []
                if self.topics is None:
                    self.topics = []

        papers = mock_papers + [DupPaper()]
        result = _deduplicate_papers(papers)
        dois = [p.ids.doi for p in result if p.ids.doi]
        assert dois.count("10.1234/test.2024") == 1

    def test_removes_title_duplicates(self, mock_papers):
        # mock_papers[0] and mock_papers[3] have similar titles
        result = _deduplicate_papers(mock_papers)
        assert len(result) < len(mock_papers)


class TestIsTitleDuplicate:
    def test_exact_match(self):
        assert _is_title_duplicate("Hello World", ["Hello World"])

    def test_near_match(self):
        assert _is_title_duplicate(
            "Deep Learning for Proteins",
            ["Deep Learning for Protein Structure"],
        ) is False  # Different enough

    def test_empty_list(self):
        assert _is_title_duplicate("Anything", []) is False


class TestComputeRecencyScore:
    def test_current_year_gets_max(self):
        assert _compute_recency_score(2026, 2026) == pytest.approx(1.0)

    def test_old_paper_gets_low_score(self):
        score = _compute_recency_score(2000, 2026)
        assert score < 0.2

    def test_none_year_gets_neutral(self):
        assert _compute_recency_score(None, 2026) == 0.3

    def test_minimum_floor(self):
        assert _compute_recency_score(1950, 2026) >= 0.1


class TestComputeCitationScore:
    def test_zero_citations(self):
        assert _compute_citation_score(0) == 0.0

    def test_high_citations(self):
        score = _compute_citation_score(5000)
        assert 0.5 < score < 1.0

    def test_very_high_citations(self):
        assert _compute_citation_score(100000) == 1.0

    def test_moderate_citations(self):
        score = _compute_citation_score(100)
        assert 0.2 < score < 0.6


class TestMakeUniqueCiteKey:
    def test_basic_key(self, mock_paper):
        key = _make_unique_cite_key(mock_paper, set())
        assert "smith" in key.lower()
        assert "2023" in key

    def test_handles_collision(self, mock_paper):
        existing = {"smith2023deep"}
        key = _make_unique_cite_key(mock_paper, existing)
        assert key != "smith2023deep"
        assert key.startswith("smith2023deep")

    def test_handles_no_author(self):
        from dataclasses import dataclass

        @dataclass
        class NoAuthorPaper:
            title: str = "A Paper"
            authors: list = None
            year: int = 2023
            ids: object = None

            def __post_init__(self):
                if self.authors is None:
                    self.authors = []

        key = _make_unique_cite_key(NoAuthorPaper(), set())
        assert "unknown" in key


class TestFirstAlphaWord:
    def test_skips_articles(self):
        assert _first_alpha_word("The Deep Learning Approach") == "deep"

    def test_returns_first_non_article(self):
        assert _first_alpha_word("Protein Structure") == "protein"

    def test_empty_string(self):
        assert _first_alpha_word("") == ""


class TestToAscii:
    def test_removes_non_ascii(self):
        assert _to_ascii("Müller2023") == "Muller2023"

    def test_removes_special_chars(self):
        assert _to_ascii("smith-2023_paper") == "smith2023paper"


class TestFilterAndRank:
    def test_returns_requested_count(self, mock_papers, sample_keywords, sample_document):
        result = filter_and_rank(mock_papers, sample_keywords, sample_document, num_refs=2)
        assert len(result) == 2

    def test_sorted_by_relevance(self, mock_papers, sample_keywords, sample_document):
        result = filter_and_rank(mock_papers, sample_keywords, sample_document, num_refs=5)
        scores = [sp.relevance_score for sp in result]
        assert scores == sorted(scores, reverse=True)

    def test_empty_input(self, sample_keywords, sample_document):
        result = filter_and_rank([], sample_keywords, sample_document, num_refs=5)
        assert result == ()

    def test_unique_cite_keys(self, mock_papers, sample_keywords, sample_document):
        result = filter_and_rank(mock_papers, sample_keywords, sample_document, num_refs=10)
        keys = [sp.cite_key for sp in result]
        assert len(keys) == len(set(keys))


class TestKeywordOverlapReturnType:
    def test_returns_score_and_count(self, mock_paper, sample_keywords):
        result = _compute_keyword_overlap(mock_paper, sample_keywords)
        assert isinstance(result, tuple)
        assert len(result) == 2
        score, count = result
        assert isinstance(score, float)
        assert isinstance(count, int)
        assert 0.0 <= score <= 1.0
        assert count >= 0

    def test_count_matches_expected(self, mock_paper, sample_keywords):
        # mock_paper has "deep learning", "protein structure prediction",
        # "transformer" in title+abstract
        _score, count = _compute_keyword_overlap(mock_paper, sample_keywords)
        assert count >= 2  # at least deep learning + protein structure prediction


class TestFilterThreshold:
    def test_filters_irrelevant_paper(self, sample_keywords, sample_document):
        """A paper with no keyword matches should be filtered out."""
        from dataclasses import dataclass

        @dataclass
        class IrrelevantIDSet:
            doi: str = "10.9999/irrelevant"
            pmid: str = ""
            pmcid: str = ""
            openalex_id: str = ""
            s2_id: str = ""
            arxiv_id: str = ""

        @dataclass
        class IrrelevantAuthor:
            name: str = "Nobody"
            family_name: str = "Nobody"
            given_name: str = "A"
            orcid: str = ""
            openalex_id: str = ""
            s2_id: str = ""

            def citation_name(self) -> str:
                return "Nobody, A."

        @dataclass
        class IrrelevantPaper:
            title: str = "YOLOv10: Real-Time Object Detection"
            authors: list = None
            year: int = 2024
            abstract: str = "We present improvements to the YOLO architecture for faster detection."
            citation_count: int = 50000
            ids: IrrelevantIDSet = None
            keywords: list = None
            url: str = ""
            pdf_locations: list = None
            is_oa: bool = False
            influential_citation_count: int = 0
            is_retracted: bool = False
            source_venue: object = None
            publication_date: str = ""
            pub_type: str = "article"
            tldr: str = ""
            mesh_terms: list = None
            topics: list = None
            _bibtex: str = ""

            def __post_init__(self):
                if self.authors is None:
                    self.authors = [IrrelevantAuthor()]
                if self.ids is None:
                    self.ids = IrrelevantIDSet()
                if self.keywords is None:
                    self.keywords = []
                if self.pdf_locations is None:
                    self.pdf_locations = []
                if self.mesh_terms is None:
                    self.mesh_terms = []
                if self.topics is None:
                    self.topics = []

        result = filter_and_rank(
            [IrrelevantPaper()], sample_keywords, sample_document, num_refs=10
        )
        # Irrelevant paper should be filtered out despite high citations
        assert len(result) == 0

    def test_relaxed_threshold_few_keywords(self, mock_paper, sample_document):
        """With < 5 keywords, papers matching only 1 keyword should still pass."""
        few_keywords = ExtractedKeywords(
            keywords=(
                ("deep learning", 0.9),
                ("protein structure", 0.8),
            ),
            source_method="test",
        )
        result = filter_and_rank([mock_paper], few_keywords, sample_document, num_refs=5)
        assert len(result) >= 1
