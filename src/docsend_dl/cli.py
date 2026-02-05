"""Command-line interface for docsend-dl."""

from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
import time
from pathlib import Path

from . import _resolve_pdf_path
from .assembler import assemble_pdf
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
        description=(
            "Download all slides from a public DocSend deck as a PDF (default)"
            " or individual PNG images."
        ),
    )
    parser.add_argument(
        "url",
        help="DocSend deck URL (e.g. https://docsend.com/view/XXXXXX)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Output path. In PDF mode (default): a .pdf file path, a"
            " directory, or omit for {title}.pdf in CWD. In --images mode:"
            " output directory (default: deck title in CWD)."
        ),
    )
    parser.add_argument(
        "--images",
        action="store_true",
        default=False,
        help="Save individual PNG images instead of a single PDF",
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

    if args.images:
        output_dir: Path = args.output or Path(deck_info.title)
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
    else:
        pdf_path = _resolve_pdf_path(
            output=args.output,
            deck_title=deck_info.title,
        )

        print("Downloading slides...")
        with tempfile.TemporaryDirectory(prefix="docsend_") as tmp_dir:
            tmp_path = Path(tmp_dir)

            result = await download_slides(
                urls=deck_info.image_urls,
                output_dir=tmp_path,
            )

            image_paths = sorted(tmp_path.glob("slide_*.png"))

            pdf_size = 0
            if image_paths:
                print("Assembling PDF...")
                pdf_size = assemble_pdf(
                    image_paths=image_paths,
                    output_path=pdf_path,
                )

        elapsed = time.monotonic() - start_time

        print()
        print(f"Done in {elapsed:.1f}s")
        print(f"  Slides saved: {result.successes}/{deck_info.slide_count}")
        if result.failures:
            print(f"  Failed: {result.failures}")
            for name in result.failed_slides:
                print(f"    - {name}")
        print(f"  PDF size: {_format_size(pdf_size)}")
        print(f"  Output: {pdf_path}")

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
