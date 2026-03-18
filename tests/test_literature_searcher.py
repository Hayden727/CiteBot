"""Tests for the literature searcher query construction."""

import pytest

from citebot.literature_searcher import (
    _build_search_queries,
    _is_technical_term,
    _quote_phrase,
)
from citebot.types import ExtractedKeywords


class TestQuotePhrase:
    def test_quotes_multi_word(self):
        assert _quote_phrase("deep learning") == '"deep learning"'

    def test_no_quotes_single_word(self):
        assert _quote_phrase("BERT") == "BERT"


class TestIsTechnicalTerm:
    def test_rejects_generic_words(self):
        for word in ("model", "system", "analysis", "framework", "network", "optimization"):
            assert not _is_technical_term(word), f"{word} should be generic"

    def test_accepts_domain_terms(self):
        for word in ("BERT", "GAN", "MLIR", "pytorch", "tensorflow", "bioinformatics"):
            assert _is_technical_term(word), f"{word} should be technical"

    def test_rejects_short_words(self):
        assert not _is_technical_term("ab")
        assert not _is_technical_term("x")

    def test_accepts_medium_length_terms(self):
        assert _is_technical_term("LSTM")
        assert _is_technical_term("CUDA")


class TestBuildSearchQueries:
    def test_empty_keywords(self):
        kw = ExtractedKeywords(keywords=(), source_method="test")
        assert _build_search_queries(kw) == ()

    def test_broad_tier_uses_short_keywords_unquoted(self):
        kw = ExtractedKeywords(
            keywords=(("BERT", 0.9), ("NLP", 0.8), ("tokenization", 0.7)),
            source_method="test",
        )
        queries = _build_search_queries(kw)
        # First query should be broad: unquoted short keywords sorted by searchability
        # NLP (3 chars, uppercase) before BERT (4 chars, uppercase) before tokenization
        assert queries[0] == "NLP BERT tokenization"

    def test_medium_tier_mixes_short_and_phrase(self):
        kw = ExtractedKeywords(
            keywords=(
                ("BERT", 0.9),
                ("text classification", 0.8),
                ("sentiment analysis", 0.7),
            ),
            source_method="test",
        )
        queries = _build_search_queries(kw)
        # Should have a query mixing short keyword with quoted phrase
        assert any(
            "BERT" in q and '"text classification"' in q
            for q in queries
        )

    def test_targeted_tier_quotes_phrases(self):
        kw = ExtractedKeywords(
            keywords=(
                ("graph neural network", 0.9),
                ("node embedding", 0.8),
            ),
            source_method="test",
        )
        queries = _build_search_queries(kw)
        assert any(q == '"graph neural network"' for q in queries)

    def test_technical_singles_included(self):
        kw = ExtractedKeywords(
            keywords=(("BERT", 0.9), ("transformer", 0.8)),
            source_method="test",
        )
        queries = _build_search_queries(kw, max_queries=10)
        assert any(q == "BERT" for q in queries)
        assert any(q == "transformer" for q in queries)

    def test_generic_singles_excluded_from_targeted(self):
        kw = ExtractedKeywords(
            keywords=(("model", 0.9), ("network", 0.8), ("system", 0.7)),
            source_method="test",
        )
        queries = _build_search_queries(kw, max_queries=10)
        # Generic words should not appear as standalone targeted queries
        standalone = [q for q in queries if q in ("model", "network", "system")]
        assert len(standalone) == 0

    def test_no_duplicates(self):
        kw = ExtractedKeywords(
            keywords=(("BERT", 0.9), ("attention mechanism", 0.8)),
            source_method="test",
        )
        queries = _build_search_queries(kw, max_queries=20)
        assert len(queries) == len(set(queries))

    def test_all_phrases_fallback(self):
        """When all keywords are multi-word, still produces queries."""
        kw = ExtractedKeywords(
            keywords=(
                ("deep learning", 0.9),
                ("neural network", 0.8),
                ("batch normalization", 0.7),
            ),
            source_method="test",
        )
        queries = _build_search_queries(kw)
        assert len(queries) > 0

    def test_scales_for_large_keyword_sets(self):
        kw = ExtractedKeywords(
            keywords=tuple((f"keyword{i}", 1.0 - i * 0.05) for i in range(20)),
            source_method="test",
        )
        queries = _build_search_queries(kw)
        assert len(queries) >= 5
