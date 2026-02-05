"""docsend-dl: Download slides from public DocSend decks as PDF or PNG images."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from .assembler import assemble_pdf
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
    "DeckDownloadResult",
    "DeckInfo",
    "DocSendError",
    "DownloadResult",
    "EmailGateError",
    "ExtractionError",
    "InvalidURLError",
    "assemble_pdf",
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
    output_path: Path


def _resolve_pdf_path(
    *,
    output: Path | str | None,
    deck_title: str,
) -> Path:
    """Resolve the output PDF file path.

    Rules:
        - ``None`` → ``{cwd}/{deck_title}.pdf``
        - Ends in ``.pdf`` → treated as literal file path
        - Otherwise → treated as directory: ``{path}/{deck_title}.pdf``
    """
    if output is None:
        return Path(f"{deck_title}.pdf").resolve()

    output = Path(output)
    if output.suffix.lower() == ".pdf":
        return output.resolve()

    return (output / f"{deck_title}.pdf").resolve()


async def download_deck(
    url: str,
    output: Path | str | None = None,
    *,
    headless: bool = True,
    concurrency: int = 10,
    max_retries: int = 3,
    images_only: bool = False,
) -> DeckDownloadResult:
    """Download all slides from a public DocSend deck.

    This is the high-level convenience function that combines URL extraction
    and image downloading into a single call.

    By default the slides are assembled into a single PDF.  Pass
    ``images_only=True`` to save individual PNG files instead.

    Args:
        url: Full DocSend URL (e.g. ``https://docsend.com/view/XXXXXX``).
        output: Output path.  In PDF mode this follows smart resolution:
            omit for ``{title}.pdf`` in the CWD, pass a ``.pdf`` path to use
            it literally, or pass a directory to save ``{title}.pdf`` inside it.
            In images mode this is the output directory (defaults to the deck
            title in the CWD).
        headless: Run the browser in headless mode. Defaults to True.
        concurrency: Maximum number of concurrent image downloads.
        max_retries: Number of retry attempts per image download.
        images_only: Save individual PNG images instead of a PDF.

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
        ))
        print(f"Saved PDF to {result.output_path}")
    """
    deck_info = await extract_slide_urls(url=url, headless=headless)

    if images_only:
        resolved_dir = Path(output) if output else Path(deck_info.title)
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
            output_path=resolved_dir,
        )

    pdf_path = _resolve_pdf_path(output=output, deck_title=deck_info.title)

    with tempfile.TemporaryDirectory(prefix="docsend_") as tmp_dir:
        tmp_path = Path(tmp_dir)

        dl_result = await download_slides(
            urls=deck_info.image_urls,
            output_dir=tmp_path,
            concurrency=concurrency,
            max_retries=max_retries,
        )

        image_paths = sorted(tmp_path.glob("slide_*.png"))

        if not image_paths:
            return DeckDownloadResult(
                deck_title=deck_info.title,
                slide_count=deck_info.slide_count,
                successes=0,
                failures=dl_result.failures,
                total_bytes=0,
                failed_slides=dl_result.failed_slides,
                output_path=pdf_path,
            )

        pdf_size = assemble_pdf(
            image_paths=image_paths,
            output_path=pdf_path,
        )

    return DeckDownloadResult(
        deck_title=deck_info.title,
        slide_count=deck_info.slide_count,
        successes=dl_result.successes,
        failures=dl_result.failures,
        total_bytes=pdf_size,
        failed_slides=dl_result.failed_slides,
        output_path=pdf_path,
    )
