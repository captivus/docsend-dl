"""Command-line interface for docsend-dl."""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

from .downloader import download_slides
from .extractor import (
    DocSendError,
    extract_slide_urls,
)


def _format_size(num_bytes: int) -> str:
    """Format a byte count as a human-readable string."""
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if abs(value) < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docsend-dl",
        description="Download all slides from a public DocSend deck as PNG images.",
    )
    parser.add_argument(
        "url",
        help="DocSend deck URL (e.g. https://docsend.com/view/XXXXXX)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: deck title in current directory)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run browser in headless mode (default: True)",
    )
    parser.add_argument(
        "--no-headless",
        action="store_false",
        dest="headless",
        help="Show the browser window during download",
    )
    return parser


async def _async_main(args: argparse.Namespace) -> None:
    start_time = time.monotonic()

    print("Loading DocSend page...")
    deck_info = await extract_slide_urls(url=args.url, headless=args.headless)
    print(f'Found deck: "{deck_info.title}" ({deck_info.slide_count} slides)')

    for warning in deck_info.warnings:
        print(f"  Warning: {warning}", file=sys.stderr)

    valid_count = sum(1 for u in deck_info.image_urls if u)
    print(f"Got {valid_count}/{deck_info.slide_count} image URLs")

    output_dir: Path = args.output_dir or Path(deck_info.title)
    output_dir = output_dir.resolve()

    print(f"Downloading slides to: {output_dir}")
    result = await download_slides(
        urls=deck_info.image_urls,
        output_dir=output_dir,
    )

    elapsed = time.monotonic() - start_time

    print()
    print(f"Done in {elapsed:.1f}s")
    print(f"  Slides saved: {result.successes}/{deck_info.slide_count}")
    if result.failures:
        print(f"  Failed: {result.failures}")
        for name in result.failed_slides:
            print(f"    - {name}")
    print(f"  Total size: {_format_size(result.total_bytes)}")
    print(f"  Output: {output_dir}")

    if result.failures:
        sys.exit(1)


def main() -> None:
    """Entry point for the ``docsend-dl`` CLI command."""
    parser = _build_parser()
    args = parser.parse_args()

    try:
        asyncio.run(_async_main(args=args))
    except DocSendError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
