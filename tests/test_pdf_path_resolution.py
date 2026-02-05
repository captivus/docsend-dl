"""Unit tests for PDF path resolution logic — no network required."""

from __future__ import annotations

from pathlib import Path

from docsend_dl import _resolve_pdf_path


class TestResolvePdfPath:
    def test_none_uses_cwd_with_title(self):
        result = _resolve_pdf_path(output=None, deck_title="My Deck")
        assert result.name == "My Deck.pdf"
        assert result.is_absolute()

    def test_pdf_suffix_treated_as_file(self, tmp_path: Path):
        result = _resolve_pdf_path(
            output=str(tmp_path / "custom.pdf"),
            deck_title="My Deck",
        )
        assert result == (tmp_path / "custom.pdf").resolve()

    def test_directory_gets_title_appended(self, tmp_path: Path):
        result = _resolve_pdf_path(
            output=str(tmp_path),
            deck_title="My Deck",
        )
        assert result == (tmp_path / "My Deck.pdf").resolve()

    def test_pdf_suffix_case_insensitive(self, tmp_path: Path):
        result = _resolve_pdf_path(
            output=str(tmp_path / "custom.PDF"),
            deck_title="My Deck",
        )
        assert result == (tmp_path / "custom.PDF").resolve()

    def test_string_output_converted_to_path(self):
        result = _resolve_pdf_path(output="some/dir", deck_title="Deck")
        assert result.name == "Deck.pdf"
        assert result.is_absolute()

    def test_path_output_accepted(self, tmp_path: Path):
        result = _resolve_pdf_path(
            output=tmp_path / "out",
            deck_title="Deck",
        )
        assert result == (tmp_path / "out" / "Deck.pdf").resolve()

    def test_nested_directory_with_pdf_filename(self, tmp_path: Path):
        result = _resolve_pdf_path(
            output=str(tmp_path / "subdir" / "report.pdf"),
            deck_title="My Deck",
        )
        assert result == (tmp_path / "subdir" / "report.pdf").resolve()
