"""Integration tests that download real DocSend decks and verify checksums.

These tests require network access and a working Playwright/Chromium setup.
Mark with ``pytest -m integration`` to run selectively.
"""

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from docsend_dl import download_deck, extract_slide_urls
from docsend_dl.downloader import download_slides

REFERENCE_FILE = Path(__file__).parent / "reference_checksums.json"

pytestmark = pytest.mark.integration


def _load_reference() -> dict:
    with open(REFERENCE_FILE) as f:
        return json.load(f)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


class TestExtraction:
    """Test URL extraction for both reference decks."""

    @pytest.mark.asyncio
    async def test_extract_n43v89r(self):
        ref = _load_reference()["n43v89r"]
        deck_info = await extract_slide_urls(
            url=ref["url"],
            headless=True,
        )
        assert deck_info.slide_count == ref["slide_count"]
        assert len(deck_info.image_urls) == ref["slide_count"]
        assert all(u is not None for u in deck_info.image_urls)

    @pytest.mark.asyncio
    async def test_extract_p8jxsqr(self):
        ref = _load_reference()["p8jxsqr"]
        deck_info = await extract_slide_urls(
            url=ref["url"],
            headless=True,
        )
        assert deck_info.slide_count == ref["slide_count"]
        assert len(deck_info.image_urls) == ref["slide_count"]
        assert all(u is not None for u in deck_info.image_urls)


class TestDownloadAndChecksum:
    """Test full download + SHA256 checksum verification."""

    @pytest.mark.asyncio
    async def test_deck_n43v89r(self):
        ref = _load_reference()["n43v89r"]
        tmp_dir = Path(tempfile.mkdtemp(prefix="docsend_test_"))

        try:
            deck_info = await extract_slide_urls(url=ref["url"], headless=True)
            result = await download_slides(
                urls=deck_info.image_urls,
                output_dir=tmp_dir,
            )

            assert result.failures == 0
            assert result.successes == ref["slide_count"]

            for filename, expected_hash in ref["checksums"].items():
                actual_hash = _sha256(path=tmp_dir / filename)
                assert actual_hash == expected_hash, f"Checksum mismatch for {filename}"
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_deck_p8jxsqr(self):
        ref = _load_reference()["p8jxsqr"]
        tmp_dir = Path(tempfile.mkdtemp(prefix="docsend_test_"))

        try:
            deck_info = await extract_slide_urls(url=ref["url"], headless=True)
            result = await download_slides(
                urls=deck_info.image_urls,
                output_dir=tmp_dir,
            )

            assert result.failures == 0
            assert result.successes == ref["slide_count"]

            for filename, expected_hash in ref["checksums"].items():
                actual_hash = _sha256(path=tmp_dir / filename)
                assert actual_hash == expected_hash, f"Checksum mismatch for {filename}"
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class TestHighLevelAPI:
    """Test the download_deck convenience function."""

    @pytest.mark.asyncio
    async def test_download_deck(self):
        ref = _load_reference()["n43v89r"]
        tmp_dir = Path(tempfile.mkdtemp(prefix="docsend_test_"))

        try:
            result = await download_deck(
                url=ref["url"],
                output_dir=tmp_dir,
            )

            assert result.successes == ref["slide_count"]
            assert result.failures == 0
            assert result.slide_count == ref["slide_count"]
            assert result.total_bytes > 0
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
