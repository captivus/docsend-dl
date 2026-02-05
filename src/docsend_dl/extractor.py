"""Playwright-based extraction of slide image URLs from DocSend decks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout


DOCSEND_URL_PATTERN = re.compile(
    r"https?://(?:dbx\.)?docsend\.com/view/([a-zA-Z0-9]+)"
)

_PAGE_DATA_BATCH_SIZE = 10

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# JavaScript executed inside the browser to extract slide URLs.
# Fetches all page_data endpoints (same-origin) and returns the
# directImageUrl (S3 signed URL) for each slide.
_EXTRACT_URLS_JS = """
async (args) => {
    const { slug, slideCount, batchSize } = args;
    const ts = Math.floor(Date.now() / 1000);
    const urls = new Array(slideCount);
    const errors = [];

    const totalBatches = Math.ceil(slideCount / batchSize);
    for (let batch = 0; batch < totalBatches; batch++) {
        const start = batch * batchSize;
        const end = Math.min(start + batchSize, slideCount);
        const promises = [];

        for (let i = start; i < end; i++) {
            promises.push(
                fetch(`/view/${slug}/page_data/${i + 1}?timezoneOffset=-21600&viewLoadTime=${ts}`)
                    .then(r => {
                        if (!r.ok) throw new Error('HTTP ' + r.status);
                        return r.json();
                    })
                    .then(data => {
                        urls[i] = data.directImageUrl || null;
                    })
                    .catch(e => {
                        urls[i] = null;
                        errors.push(`Slide ${i + 1}: ${e.message}`);
                    })
            );
        }
        await Promise.all(promises);
    }

    return { urls, errors };
}
"""

# JavaScript to extract the slide count and deck title from the page.
_EXTRACT_INFO_JS = """
() => {
    const items = document.querySelectorAll('.carousel-inner .item');
    const slideCount = items.length;

    let title = '';

    const ogTitle = document.querySelector('meta[property="og:title"]');
    if (ogTitle) {
        const og = ogTitle.getAttribute('content') || '';
        if (og && !og.toLowerCase().includes('docsend')) {
            title = og;
        }
    }

    if (!title) {
        const dt = document.title
            .replace(/\\s*[-\\u2013|]\\s*DocSend.*/i, '')
            .trim();
        if (dt && !dt.toLowerCase().includes('docsend')) {
            title = dt;
        }
    }

    if (!title) {
        const slug = window.location.pathname.split('/view/')[1];
        if (slug) title = 'docsend-' + slug.split('/')[0];
    }

    return { slideCount, title };
}
"""


class DocSendError(Exception):
    """Base exception for docsend-dl errors."""


class InvalidURLError(DocSendError):
    """Raised when the provided URL is not a valid DocSend URL."""


class EmailGateError(DocSendError):
    """Raised when the deck requires email verification to view."""


class ExtractionError(DocSendError):
    """Raised when slide content cannot be found or extracted."""


@dataclass
class DeckInfo:
    """Information extracted from a DocSend deck."""

    title: str
    slide_count: int
    image_urls: list[str | None]
    warnings: list[str] = field(default_factory=list)


def parse_docsend_url(url: str) -> str:
    """Validate a DocSend URL and return the document slug.

    Raises:
        InvalidURLError: If the URL doesn't match the expected pattern.
    """
    match = DOCSEND_URL_PATTERN.match(url)
    if not match:
        raise InvalidURLError(
            f"Invalid DocSend URL: {url}\n"
            "Expected format: https://docsend.com/view/XXXXXX "
            "or https://dbx.docsend.com/view/XXXXXX"
        )
    return match.group(1)


async def extract_slide_urls(
    url: str,
    *,
    headless: bool = True,
) -> DeckInfo:
    """Navigate to a DocSend deck and extract S3 image URLs for all slides.

    Uses a headless Chromium browser via Playwright to load the page, then
    fetches each slide's ``page_data`` endpoint from within the browser
    context (same-origin request, bypasses bot detection). Returns the
    ``directImageUrl`` (S3 signed URL) for each slide.

    Args:
        url: Full DocSend URL (e.g. ``https://docsend.com/view/XXXXXX``).
        headless: Run browser in headless mode. Defaults to True.

    Returns:
        A :class:`DeckInfo` with the deck title, slide count, and image URLs.

    Raises:
        InvalidURLError: If the URL is not a valid DocSend URL.
        EmailGateError: If the deck requires email verification.
        ExtractionError: If slides cannot be found on the page.
    """
    slug = parse_docsend_url(url=url)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = await browser.new_context(
            user_agent=_USER_AGENT,
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        await page.add_init_script(
            'Object.defineProperty(navigator, "webdriver", { get: () => undefined });'
        )

        try:
            await page.goto(url, wait_until="networkidle", timeout=30_000)
        except PlaywrightTimeout:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)

        try:
            await page.wait_for_selector(".carousel-inner .item", timeout=15_000)
        except PlaywrightTimeout:
            email_form = await page.query_selector(
                'input[type="email"], form[action*="email"], .visitor-email'
            )
            await browser.close()
            if email_form:
                raise EmailGateError(
                    "This deck requires email verification to view. "
                    "Only public (no-email) decks are supported."
                )
            raise ExtractionError(
                "Could not find slide content on the page. "
                "The page may have changed structure or failed to load."
            )

        info = await page.evaluate(_EXTRACT_INFO_JS)
        slide_count: int = info["slideCount"]
        deck_title: str = info["title"] or "DocSend Deck"

        if slide_count == 0:
            await browser.close()
            raise ExtractionError("No slides found in this deck.")

        result = await page.evaluate(
            _EXTRACT_URLS_JS,
            {
                "slug": slug,
                "slideCount": slide_count,
                "batchSize": _PAGE_DATA_BATCH_SIZE,
            },
        )

        await browser.close()

        urls: list[str | None] = result["urls"]
        warnings: list[str] = result["errors"]

        valid_count = sum(1 for u in urls if u)
        if valid_count == 0:
            raise ExtractionError("Could not retrieve any image URLs from page_data endpoints.")

        return DeckInfo(
            title=deck_title,
            slide_count=slide_count,
            image_urls=urls,
            warnings=warnings,
        )
