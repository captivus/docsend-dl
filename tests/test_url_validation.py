"""Unit tests for URL parsing — no network required."""

import pytest

from docsend_dl.extractor import (
    InvalidURLError,
    _extract_view_slug,
    parse_docsend_url,
)


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

    def test_v_format_returns_none(self):
        slug = parse_docsend_url(url="https://docsend.com/v/abc12/my-document")
        assert slug is None

    def test_v_format_dbx_subdomain(self):
        slug = parse_docsend_url(url="https://dbx.docsend.com/v/abc12/my-document")
        assert slug is None

    def test_v_format_http_scheme(self):
        slug = parse_docsend_url(url="http://docsend.com/v/abc12/my-doc")
        assert slug is None

    def test_v_format_with_hyphens_in_name(self):
        slug = parse_docsend_url(url="https://docsend.com/v/abc12/my-long-name-here")
        assert slug is None

    def test_invalid_domain(self):
        with pytest.raises(InvalidURLError):
            parse_docsend_url(url="https://example.com/view/abc123")

    def test_missing_slug(self):
        with pytest.raises(InvalidURLError):
            parse_docsend_url(url="https://docsend.com/view/")

    def test_v_format_missing_name_segment(self):
        with pytest.raises(InvalidURLError):
            parse_docsend_url(url="https://docsend.com/v/abc12")

    def test_v_format_missing_both_segments(self):
        with pytest.raises(InvalidURLError):
            parse_docsend_url(url="https://docsend.com/v/")

    def test_completely_invalid(self):
        with pytest.raises(InvalidURLError):
            parse_docsend_url(url="not-a-url")

    def test_empty_string(self):
        with pytest.raises(InvalidURLError):
            parse_docsend_url(url="")


class TestExtractViewSlug:
    def test_standard_view_url(self):
        assert _extract_view_slug(url="https://docsend.com/view/abc123") == "abc123"

    def test_dbx_subdomain(self):
        assert _extract_view_slug(url="https://dbx.docsend.com/view/xyz789") == "xyz789"

    def test_with_query_params(self):
        assert _extract_view_slug(url="https://docsend.com/view/abc123?foo=bar") == "abc123"

    def test_no_view_path(self):
        assert _extract_view_slug(url="https://docsend.com/v/space/name") is None

    def test_empty_string(self):
        assert _extract_view_slug(url="") is None
