"""Tests for the BibTeX generator module."""

import pytest

from citebot.bib_generator import _replace_cite_key, _validate_bibtex


class TestReplaceCiteKey:
    def test_replaces_key(self):
        entry = "@article{old_key, title={Test}}"
        result = _replace_cite_key(entry, "new_key")
        assert "@article{new_key," in result
        assert "old_key" not in result

    def test_handles_inproceedings(self):
        entry = "@inproceedings{smith2020, title={Test}}"
        result = _replace_cite_key(entry, "doe2021deep")
        assert "@inproceedings{doe2021deep," in result

    def test_preserves_content(self):
        entry = "@article{key, title={My Title}, author={John}}"
        result = _replace_cite_key(entry, "newkey")
        assert "My Title" in result
        assert "John" in result


class TestValidateBibtex:
    def test_valid_bibtex(self):
        content = "@article{test, title={Test}, author={Doe}, year={2023}}\n"
        result = _validate_bibtex(content)
        assert result == content

    def test_returns_content_even_if_malformed(self):
        content = "@article{test, title missing braces}\n"
        # Should return content (graceful) not raise
        result = _validate_bibtex(content)
        assert result == content
