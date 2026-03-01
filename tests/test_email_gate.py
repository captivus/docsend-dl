"""Unit tests for email-gate support — no network required.

These tests mock the Playwright browser to verify the email-gate handling
logic in ``extract_slide_urls`` as well as the CLI and high-level API
pass-through of the ``email`` parameter.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from docsend_dl.extractor import (
    EmailGateError,
    ExtractionError,
    PlaywrightTimeout,
    extract_slide_urls,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_page(
    *,
    primary_email_input: bool = False,
    fallback_email_input: bool = False,
    has_continue_btn: bool = False,
    slides_load_after_email: bool = True,
):
    """Build a mock Playwright page that simulates email-gate scenarios.

    Returns ``(page, mocks)`` where *mocks* is a dict with references to
    the internal mock objects (``email_input``, ``continue_btn``) so that
    tests can assert on them directly without re-entering the side-effect.

    Args:
        primary_email_input: ``#link_auth_form_email`` is present.
        fallback_email_input: ``input.js-auth-form_email-field`` is present.
        has_continue_btn: Whether a "Continue" button is present.
        slides_load_after_email: Whether slides load after submitting email.
    """
    page = AsyncMock()
    page.url = "https://docsend.com/view/abc123"

    # Counter keyed by selector so different selectors don't interfere.
    carousel_call_count = 0

    async def _wait_for_selector(selector, **kwargs):
        nonlocal carousel_call_count
        if selector == ".carousel-inner .item":
            carousel_call_count += 1
            if carousel_call_count == 1:
                raise PlaywrightTimeout("Timeout")
            if not slides_load_after_email:
                raise PlaywrightTimeout("Timeout")
            return MagicMock()
        return MagicMock()

    page.wait_for_selector = AsyncMock(side_effect=_wait_for_selector)

    primary_mock = AsyncMock() if primary_email_input else None
    fallback_mock = AsyncMock() if fallback_email_input else None
    # Use the primary mock as the canonical email input; if only fallback
    # is set, that becomes the one the implementation interacts with.
    email_input_mock = primary_mock or fallback_mock
    continue_btn_mock = AsyncMock() if has_continue_btn else None

    async def _query_selector(selector):
        if selector == "#link_auth_form_email":
            return primary_mock
        if selector == "input.js-auth-form_email-field":
            return fallback_mock
        if selector == 'button:has-text("Continue")':
            return continue_btn_mock
        return None

    page.query_selector = AsyncMock(side_effect=_query_selector)

    # Distinguish info vs batch calls by whether an arg dict is passed
    # (mirrors the real call signatures in extractor.py lines 267/285).
    async def _evaluate(js, arg=None):
        if arg is None:
            return {"slideCount": 2, "title": "Test Deck"}
        return {
            "urls": [
                {"index": arg["batchStart"], "url": "https://s3.example.com/slide1.png"},
                {"index": arg["batchStart"] + 1, "url": "https://s3.example.com/slide2.png"},
            ],
            "errors": [],
        }

    page.evaluate = AsyncMock(side_effect=_evaluate)

    mocks = {
        "email_input": email_input_mock,
        "continue_btn": continue_btn_mock,
    }
    return page, mocks


def _build_playwright_mocks(page: AsyncMock):
    """Return (browser_mock, playwright_context_manager) wired to *page*."""
    browser = AsyncMock()
    context = AsyncMock()
    context.new_page.return_value = page
    browser.new_context.return_value = context

    pw = AsyncMock()
    pw.chromium.launch.return_value = browser

    pw_cm = AsyncMock()
    pw_cm.__aenter__ = AsyncMock(return_value=pw)
    pw_cm.__aexit__ = AsyncMock(return_value=False)

    return browser, pw_cm


# ---------------------------------------------------------------------------
# Extractor tests — detection
# ---------------------------------------------------------------------------

class TestEmailGateDetection:
    """Verify that email-gate detection raises the right error."""

    @pytest.mark.asyncio
    async def test_email_gate_without_email_raises(self):
        """EmailGateError is raised when no email is supplied."""
        page, _ = _make_mock_page(primary_email_input=True)
        browser, pw_cm = _build_playwright_mocks(page)

        with patch("docsend_dl.extractor.async_playwright", return_value=pw_cm):
            with pytest.raises(EmailGateError, match="--email"):
                await extract_slide_urls(
                    url="https://docsend.com/view/abc123",
                )

        browser.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_email_gate_fallback_selector_without_email_raises(self):
        """EmailGateError via fallback selector when primary is absent."""
        page, _ = _make_mock_page(
            primary_email_input=False,
            fallback_email_input=True,
        )
        browser, pw_cm = _build_playwright_mocks(page)

        with patch("docsend_dl.extractor.async_playwright", return_value=pw_cm):
            with pytest.raises(EmailGateError, match="--email"):
                await extract_slide_urls(
                    url="https://docsend.com/view/abc123",
                )

        browser.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_email_input_no_slides_raises_extraction_error(self):
        """ExtractionError is raised when there are no slides and no email form."""
        page, _ = _make_mock_page(
            primary_email_input=False,
            fallback_email_input=False,
        )
        browser, pw_cm = _build_playwright_mocks(page)

        with patch("docsend_dl.extractor.async_playwright", return_value=pw_cm):
            with pytest.raises(ExtractionError, match="Could not find slide content"):
                await extract_slide_urls(
                    url="https://docsend.com/view/abc123",
                )

        browser.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# Extractor tests — submission
# ---------------------------------------------------------------------------

class TestEmailGateSubmission:
    """Verify the email submission flow."""

    @pytest.mark.asyncio
    async def test_email_submitted_with_continue_button(self):
        """Email is filled and the Continue button is clicked."""
        page, mocks = _make_mock_page(
            primary_email_input=True,
            has_continue_btn=True,
            slides_load_after_email=True,
        )
        browser, pw_cm = _build_playwright_mocks(page)

        with patch("docsend_dl.extractor.async_playwright", return_value=pw_cm):
            deck = await extract_slide_urls(
                url="https://docsend.com/view/abc123",
                email="user@example.com",
            )

        mocks["email_input"].click.assert_awaited_once()
        mocks["email_input"].fill.assert_awaited_once_with("user@example.com")
        mocks["continue_btn"].click.assert_awaited_once()
        browser.close.assert_awaited_once()

        assert deck.title == "Test Deck"
        assert deck.slide_count == 2
        assert len(deck.image_urls) == 2

    @pytest.mark.asyncio
    async def test_email_submitted_via_fallback_selector(self):
        """Email is submitted when only the fallback selector matches."""
        page, mocks = _make_mock_page(
            primary_email_input=False,
            fallback_email_input=True,
            has_continue_btn=True,
            slides_load_after_email=True,
        )
        browser, pw_cm = _build_playwright_mocks(page)

        with patch("docsend_dl.extractor.async_playwright", return_value=pw_cm):
            deck = await extract_slide_urls(
                url="https://docsend.com/view/abc123",
                email="user@example.com",
            )

        mocks["email_input"].click.assert_awaited_once()
        mocks["email_input"].fill.assert_awaited_once_with("user@example.com")
        browser.close.assert_awaited_once()
        assert deck.slide_count == 2

    @pytest.mark.asyncio
    async def test_email_submitted_with_enter_fallback(self):
        """When no Continue button exists, Enter is pressed instead."""
        page, mocks = _make_mock_page(
            primary_email_input=True,
            has_continue_btn=False,  # continue_btn is None
            slides_load_after_email=True,
        )
        browser, pw_cm = _build_playwright_mocks(page)

        with patch("docsend_dl.extractor.async_playwright", return_value=pw_cm):
            deck = await extract_slide_urls(
                url="https://docsend.com/view/abc123",
                email="user@example.com",
            )

        mocks["email_input"].press.assert_awaited_once_with("Enter")
        browser.close.assert_awaited_once()
        assert deck.slide_count == 2

    @pytest.mark.asyncio
    async def test_email_submitted_but_slides_dont_load(self):
        """ExtractionError is raised when slides fail to load after email."""
        page, _ = _make_mock_page(
            primary_email_input=True,
            has_continue_btn=True,
            slides_load_after_email=False,
        )
        browser, pw_cm = _build_playwright_mocks(page)

        with patch("docsend_dl.extractor.async_playwright", return_value=pw_cm):
            with pytest.raises(ExtractionError, match="Submitted email but slides did not load"):
                await extract_slide_urls(
                    url="https://docsend.com/view/abc123",
                    email="user@example.com",
                )

        browser.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# CLI argument tests
# ---------------------------------------------------------------------------

class TestCLIEmailArgument:
    """Verify that ``--email`` is wired up in the CLI parser."""

    def test_email_argument_parsed(self):
        from docsend_dl.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args([
            "https://docsend.com/view/abc123",
            "--email", "user@example.com",
        ])
        assert args.email == "user@example.com"

    def test_email_defaults_to_none(self):
        from docsend_dl.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["https://docsend.com/view/abc123"])
        assert args.email is None


# ---------------------------------------------------------------------------
# High-level API pass-through test
# ---------------------------------------------------------------------------

class TestDownloadDeckEmailPassthrough:
    """Verify that ``download_deck`` forwards ``email`` to the extractor."""

    @pytest.mark.asyncio
    async def test_email_forwarded_to_extract_slide_urls(self):
        from docsend_dl import download_deck
        from docsend_dl.extractor import DeckInfo

        mock_deck = DeckInfo(
            title="Test",
            slide_count=1,
            image_urls=["https://s3.example.com/slide1.png"],
        )

        # Patch target is ``docsend_dl.extract_slide_urls`` (not
        # ``docsend_dl.extractor.extract_slide_urls``) because
        # ``download_deck`` in ``__init__.py`` references the name
        # imported into the ``docsend_dl`` namespace.
        with patch("docsend_dl.extract_slide_urls", new_callable=AsyncMock) as mock_extract, \
             patch("docsend_dl.download_slides", new_callable=AsyncMock) as mock_dl:

            mock_extract.return_value = mock_deck
            mock_dl.return_value = MagicMock(
                successes=1,
                failures=0,
                total_bytes=1024,
                failed_slides=[],
            )

            await download_deck(
                url="https://docsend.com/view/abc123",
                images_only=True,
                email="user@example.com",
            )

            mock_extract.assert_awaited_once()
            call_kwargs = mock_extract.call_args.kwargs
            assert call_kwargs["email"] == "user@example.com"
