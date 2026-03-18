"""Shared test fixtures for CiteBot tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from citebot.types import ExtractedKeywords, ScoredPaper, TexDocument

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_tex_path() -> str:
    return str(FIXTURES_DIR / "sample.tex")


@pytest.fixture
def sample_document(sample_tex_path: str) -> TexDocument:
    from citebot.latex_parser import parse_tex_file
    return parse_tex_file(sample_tex_path)


@pytest.fixture
def sample_keywords() -> ExtractedKeywords:
    return ExtractedKeywords(
        keywords=(
            ("protein structure prediction", 0.9),
            ("deep learning", 0.85),
            ("transformer architecture", 0.8),
            ("alphafold", 0.75),
            ("amino acid sequence", 0.7),
            ("neural network", 0.65),
            ("attention mechanism", 0.6),
            ("computational biology", 0.55),
        ),
        source_method="ensemble",
    )


@pytest.fixture
def mock_paper():
    """Create a minimal mock Paper object for testing."""

    @dataclass
    class MockIDSet:
        doi: str = "10.1234/test.2024"
        pmid: str = ""
        pmcid: str = ""
        openalex_id: str = ""
        s2_id: str = ""
        arxiv_id: str = ""

    @dataclass
    class MockAuthor:
        name: str = "John Smith"
        family_name: str = "Smith"
        given_name: str = "John"
        orcid: str = ""
        openalex_id: str = ""
        s2_id: str = ""

        def citation_name(self) -> str:
            return "Smith, J."

    @dataclass
    class MockPaper:
        title: str = "Deep Learning for Protein Structure Prediction"
        authors: list = None
        year: int = 2023
        abstract: str = "We present a novel deep learning approach for protein structure prediction using transformer architectures."
        citation_count: int = 150
        ids: MockIDSet = None
        keywords: list = None
        url: str = ""
        pdf_locations: list = None
        is_oa: bool = False
        influential_citation_count: int = 10
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
                self.authors = [MockAuthor()]
            if self.ids is None:
                self.ids = MockIDSet()
            if self.keywords is None:
                self.keywords = ["deep learning", "protein structure"]
            if self.pdf_locations is None:
                self.pdf_locations = []
            if self.mesh_terms is None:
                self.mesh_terms = []
            if self.topics is None:
                self.topics = []

    return MockPaper()


@pytest.fixture
def mock_papers(mock_paper):
    """Create a list of varied mock papers for ranking tests."""

    @dataclass
    class MockIDSet:
        doi: str = ""
        pmid: str = ""
        pmcid: str = ""
        openalex_id: str = ""
        s2_id: str = ""
        arxiv_id: str = ""

    @dataclass
    class MockAuthor:
        name: str = ""
        family_name: str = ""
        given_name: str = ""
        orcid: str = ""
        openalex_id: str = ""
        s2_id: str = ""

        def citation_name(self) -> str:
            return f"{self.family_name}, {self.given_name[0]}."

    @dataclass
    class MockPaper:
        title: str = ""
        authors: list = None
        year: int = 2023
        abstract: str = ""
        citation_count: int = 0
        ids: MockIDSet = None
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
                self.authors = []
            if self.ids is None:
                self.ids = MockIDSet()
            if self.keywords is None:
                self.keywords = []
            if self.pdf_locations is None:
                self.pdf_locations = []
            if self.mesh_terms is None:
                self.mesh_terms = []
            if self.topics is None:
                self.topics = []

    papers = [
        mock_paper,
        MockPaper(
            title="AlphaFold2: Protein Structure with Attention",
            authors=[MockAuthor(name="Jane Doe", family_name="Doe", given_name="Jane")],
            year=2021,
            abstract="AlphaFold uses attention mechanisms for protein folding.",
            citation_count=5000,
            ids=MockIDSet(doi="10.1038/s41586-021-03819-2"),
            keywords=["alphafold", "protein folding"],
        ),
        MockPaper(
            title="Transformer Networks in Bioinformatics",
            authors=[MockAuthor(name="Bob Lee", family_name="Lee", given_name="Bob")],
            year=2022,
            abstract="Survey of transformer architectures applied to biological sequence analysis.",
            citation_count=80,
            ids=MockIDSet(doi="10.1093/bioinformatics/btac123"),
            keywords=["transformer", "bioinformatics"],
        ),
        # Duplicate of first paper (different DOI, similar title)
        MockPaper(
            title="Deep Learning for Protein Structure Prediction: A Review",
            authors=[MockAuthor(name="John Smith", family_name="Smith", given_name="John")],
            year=2023,
            abstract="We review deep learning methods for protein structures.",
            citation_count=100,
            ids=MockIDSet(doi="10.5678/review.2023"),
            keywords=["deep learning", "protein structure"],
        ),
    ]
    return papers
