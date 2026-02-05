"""Unit tests for URL parsing — no network required."""

import pytest

from docsend_dl.extractor import InvalidURLError, parse_docsend_url


class TestParseDocsendUrl:
    def test_standard_url(self):
        slug = parse_docsend_url(url="https://docsend.com/view/abc123")
        assert slug == "abc123"

    def test_dbx_subdomain(self):
        slug = parse_docsend_url(url="https://dbx.docsend.com/view/n43v89r")
        assert slug == "n43v89r"

    def test_http_scheme(self):
        slug = parse_docsend_url(url="http://docsend.com/view/xyz789")
        assert slug == "xyz789"

    def test_alphanumeric_slug(self):
        slug = parse_docsend_url(url="https://docsend.com/view/A1b2C3d4")
        assert slug == "A1b2C3d4"

    def test_invalid_domain(self):
        with pytest.raises(InvalidURLError):
            parse_docsend_url(url="https://example.com/view/abc123")

    def test_missing_slug(self):
        with pytest.raises(InvalidURLError):
            parse_docsend_url(url="https://docsend.com/view/")

    def test_completely_invalid(self):
        with pytest.raises(InvalidURLError):
            parse_docsend_url(url="not-a-url")

    def test_empty_string(self):
        with pytest.raises(InvalidURLError):
            parse_docsend_url(url="")
