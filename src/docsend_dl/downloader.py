"""Parallel image downloading from S3 signed URLs."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

import httpx

_DEFAULT_CONCURRENCY = 10
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_TIMEOUT = 30.0


@dataclass
class DownloadResult:
    """Result of downloading slides from S3."""

    successes: int = 0
    failures: int = 0
    total_bytes: int = 0
    failed_slides: list[str] = field(default_factory=list)


async def _download_one(
    client: httpx.AsyncClient,
    url: str,
    output_path: Path,
    semaphore: asyncio.Semaphore,
    *,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    timeout: float = _DEFAULT_TIMEOUT,
) -> tuple[Path, int | None]:
    """Download a single image with retries.

    Returns:
        ``(output_path, file_size)`` on success, or ``(output_path, None)``
        on failure.
    """
    async with semaphore:
        for attempt in range(1, max_retries + 1):
            try:
                response = await client.get(url, timeout=timeout)
                response.raise_for_status()
                output_path.write_bytes(response.content)
                return output_path, len(response.content)
            except (httpx.HTTPError, OSError):
                if attempt == max_retries:
                    return output_path, None
                await asyncio.sleep(1.0 * attempt)

    return output_path, None


async def download_slides(
    urls: list[str | None],
    output_dir: Path,
    *,
    concurrency: int = _DEFAULT_CONCURRENCY,
    max_retries: int = _DEFAULT_MAX_RETRIES,
) -> DownloadResult:
    """Download all slide images from S3 signed URLs in parallel.

    Args:
        urls: List of S3 image URLs (``None`` entries are skipped).
        output_dir: Directory to save the slide PNGs.
        concurrency: Maximum number of concurrent downloads.
        max_retries: Number of retry attempts per image.

    Returns:
        A :class:`DownloadResult` summarizing the outcome.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(concurrency)
    tasks = []
    skipped = 0

    async with httpx.AsyncClient() as client:
        for i, url in enumerate(urls):
            num = f"{i + 1:02d}"
            output_path = output_dir / f"slide_{num}.png"

            if url is None:
                skipped += 1
                continue

            tasks.append(
                _download_one(
                    client=client,
                    url=url,
                    output_path=output_path,
                    semaphore=semaphore,
                    max_retries=max_retries,
                )
            )

        results = await asyncio.gather(*tasks)

    result = DownloadResult()
    for path, size in results:
        if size is not None:
            result.successes += 1
            result.total_bytes += size
        else:
            result.failures += 1
            result.failed_slides.append(path.name)

    return result
