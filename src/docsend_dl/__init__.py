"""docsend-dl: Download slides from public DocSend decks as PNG images."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from .downloader import DownloadResult, download_slides
from .extractor import (
    DeckInfo,
    DocSendError,
    EmailGateError,
    ExtractionError,
    InvalidURLError,
    extract_slide_urls,
    parse_docsend_url,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "DeckInfo",
    "DocSendError",
    "DownloadResult",
    "EmailGateError",
    "ExtractionError",
    "InvalidURLError",
    "download_deck",
    "download_slides",
    "extract_slide_urls",
    "parse_docsend_url",
]


@dataclass
class DeckDownloadResult:
    """Combined result of extracting and downloading a deck."""

    deck_title: str
    slide_count: int
    successes: int
    failures: int
    total_bytes: int
    failed_slides: list[str]


async def download_deck(
    url: str,
    output_dir: Path | str | None = None,
    *,
    headless: bool = True,
    concurrency: int = 10,
    max_retries: int = 3,
) -> DeckDownloadResult:
    """Download all slides from a public DocSend deck.

    This is the high-level convenience function that combines URL extraction
    and image downloading into a single call.

    Args:
        url: Full DocSend URL (e.g. ``https://docsend.com/view/XXXXXX``).
        output_dir: Directory to save slide PNGs. Defaults to the deck title
            in the current working directory.
        headless: Run the browser in headless mode. Defaults to True.
        concurrency: Maximum number of concurrent image downloads.
        max_retries: Number of retry attempts per image download.

    Returns:
        A :class:`DeckDownloadResult` summarizing the outcome.

    Raises:
        InvalidURLError: If the URL is not a valid DocSend URL.
        EmailGateError: If the deck requires email verification.
        ExtractionError: If slides cannot be found on the page.

    Example::

        import asyncio
        from docsend_dl import download_deck

        result = asyncio.run(download_deck(
            url="https://docsend.com/view/XXXXXX",
            output_dir="My Deck",
        ))
        print(f"Saved {result.successes} slides")
    """
    deck_info = await extract_slide_urls(url=url, headless=headless)

    resolved_dir = Path(output_dir) if output_dir else Path(deck_info.title)
    resolved_dir = resolved_dir.resolve()

    dl_result = await download_slides(
        urls=deck_info.image_urls,
        output_dir=resolved_dir,
        concurrency=concurrency,
        max_retries=max_retries,
    )

    return DeckDownloadResult(
        deck_title=deck_info.title,
        slide_count=deck_info.slide_count,
        successes=dl_result.successes,
        failures=dl_result.failures,
        total_bytes=dl_result.total_bytes,
        failed_slides=dl_result.failed_slides,
    )
