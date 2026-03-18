"""Tests for the pipeline module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from citebot.types import ExtractedKeywords, PipelineResult, TexDocument


class TestPipelineIntegration:
    """Integration tests using mocked external services."""

    @patch("citebot.pipeline.search_papers")
    @patch("citebot.pipeline.generate_bibtex_content")
    @patch("citebot.pipeline.write_bib_file")
    def test_pipeline_runs_end_to_end(
        self,
        mock_write,
        mock_bibtex,
        mock_search,
        sample_tex_path,
        mock_papers,
        tmp_path,
    ):
        from citebot.config import build_config
        from citebot.pipeline import run_pipeline

        mock_search.return_value = mock_papers
        mock_bibtex.return_value = "@article{test, title={Test}}\n"
        output_path = str(tmp_path / "refs.bib")
        mock_write.return_value = output_path

        config = build_config(
            num_refs=5,
            output=output_path,
            insert_cites=False,
        )

        result = run_pipeline(sample_tex_path, config)

        assert isinstance(result, PipelineResult)
        assert len(result.keywords.keywords) > 0
        assert len(result.papers) > 0
        assert result.inserted_cites is False
        mock_search.assert_called_once()
        mock_bibtex.assert_called_once()
