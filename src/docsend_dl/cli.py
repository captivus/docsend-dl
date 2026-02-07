"""Command-line interface for docsend-dl."""

from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TimeRemainingColumn,
)

from . import _resolve_pdf_path
from .assembler import assemble_pdf
from .downloader import DownloadResult, download_slides
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
        help=(
            "DocSend deck URL (e.g. https://docsend.com/view/XXXXXX"
            " or https://docsend.com/v/SPACE/NAME)"
        ),
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


async def _download_with_progress(
    *,
    console: Console,
    urls: list[str | None],
    output_dir: Path,
    slide_count: int,
) -> DownloadResult:
    """Download slides with a rich progress bar."""
    progress = Progress(
        SpinnerColumn(),
        "[progress.description]{task.description}",
        BarColumn(),
        MofNCompleteColumn(),
        TimeRemainingColumn(),
        console=console,
    )
    with progress:
        task_id = progress.add_task(
            description="Downloading slides",
            total=slide_count,
        )
        return await download_slides(
            urls=urls,
            output_dir=output_dir,
            on_slide_done=lambda: progress.advance(task_id=task_id),
        )


async def _async_main(args: argparse.Namespace) -> None:
    console = Console()
    start_time = time.monotonic()

    with console.status("[bold blue]Launching browser...") as status:
        deck_info = await extract_slide_urls(
            url=args.url,
            headless=args.headless,
            on_status=lambda msg: status.update(f"[bold blue]{msg}"),
        )

    console.print(
        f'Found deck: [bold]"{deck_info.title}"[/bold]'
        f" ({deck_info.slide_count} slides)"
    )

    for warning in deck_info.warnings:
        console.print(f"  [yellow]Warning:[/yellow] {warning}", stderr=True)

    valid_count = sum(1 for u in deck_info.image_urls if u)
    console.print(f"Got {valid_count}/{deck_info.slide_count} image URLs")

    if args.images:
        output_dir: Path = args.output or Path(deck_info.title)
        output_dir = output_dir.resolve()

        result = await _download_with_progress(
            console=console,
            urls=deck_info.image_urls,
            output_dir=output_dir,
            slide_count=deck_info.slide_count,
        )

        elapsed = time.monotonic() - start_time

        summary_lines = [
            f"[bold]Slides saved:[/bold] {result.successes}/{deck_info.slide_count}",
        ]
        if result.failures:
            summary_lines.append(
                f"[bold red]Failed:[/bold red] {result.failures}"
            )
            for name in result.failed_slides:
                summary_lines.append(f"  [red]- {name}[/red]")
        summary_lines.append(
            f"[bold]Total size:[/bold] {_format_size(result.total_bytes)}"
        )
        summary_lines.append(f"[bold]Output:[/bold] {output_dir}")

        console.print(Panel(
            "\n".join(summary_lines),
            title=f"[bold green]Done in {elapsed:.1f}s[/bold green]",
            border_style="green" if not result.failures else "yellow",
        ))
    else:
        pdf_path = _resolve_pdf_path(
            output=args.output,
            deck_title=deck_info.title,
        )

        with tempfile.TemporaryDirectory(prefix="docsend_") as tmp_dir:
            tmp_path = Path(tmp_dir)

            result = await _download_with_progress(
                console=console,
                urls=deck_info.image_urls,
                output_dir=tmp_path,
                slide_count=deck_info.slide_count,
            )

            image_paths = sorted(tmp_path.glob("slide_*.png"))

            pdf_size = 0
            if image_paths:
                with console.status("[bold blue]Assembling PDF..."):
                    pdf_size = assemble_pdf(
                        image_paths=image_paths,
                        output_path=pdf_path,
                    )

        elapsed = time.monotonic() - start_time

        summary_lines = [
            f"[bold]Slides saved:[/bold] {result.successes}/{deck_info.slide_count}",
        ]
        if result.failures:
            summary_lines.append(
                f"[bold red]Failed:[/bold red] {result.failures}"
            )
            for name in result.failed_slides:
                summary_lines.append(f"  [red]- {name}[/red]")
        summary_lines.append(
            f"[bold]PDF size:[/bold] {_format_size(pdf_size)}"
        )
        summary_lines.append(f"[bold]Output:[/bold] {pdf_path}")

        console.print(Panel(
            "\n".join(summary_lines),
            title=f"[bold green]Done in {elapsed:.1f}s[/bold green]",
            border_style="green" if not result.failures else "yellow",
        ))

    if result.failures:
        sys.exit(1)


def main() -> None:
    """Entry point for the ``docsend-dl`` CLI command."""
    console = Console(stderr=True)
    parser = _build_parser()
    args = parser.parse_args()

    try:
        asyncio.run(_async_main(args=args))
    except DocSendError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")
        sys.exit(130)
