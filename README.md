# docsend-dl

Download all slides from a public [DocSend](https://www.docsend.com/) deck as PNG images.

## Installation

```bash
pip install docsend-dl
playwright install chromium
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install docsend-dl
uv run playwright install chromium
```

## CLI Usage

```bash
docsend-dl https://docsend.com/view/XXXXXX
docsend-dl https://docsend.com/view/XXXXXX --output-dir "My Deck"
docsend-dl https://dbx.docsend.com/view/XXXXXX --no-headless
```

Slides are saved as `slide_01.png`, `slide_02.png`, etc. in the output directory.

## Python API

```python
import asyncio
from pathlib import Path
from docsend_dl import download_deck

result = asyncio.run(download_deck(
    url="https://docsend.com/view/XXXXXX",
    output_dir=Path("My Deck"),
))
print(f"Saved {result.successes}/{result.slide_count} slides ({result.total_bytes} bytes)")
```

For more control, use the lower-level functions:

```python
from docsend_dl import extract_slide_urls, download_slides

deck_info = await extract_slide_urls(url="https://docsend.com/view/XXXXXX")
result = await download_slides(urls=deck_info.image_urls, output_dir=Path("output"))
```

## How It Works

1. Launches a headless Chromium browser via [Playwright](https://playwright.dev/python/)
2. Navigates to the DocSend page and extracts the slide count
3. Fetches each slide's `page_data` endpoint from within the browser context (same-origin, bypasses bot detection)
4. Extracts `directImageUrl` (S3 signed URL) from each response
5. Downloads all images in parallel via [httpx](https://www.python-httpx.org/)

## Testing

Install dev dependencies and run the unit tests (fast, no network):

```bash
uv run pytest tests/test_url_validation.py
```

Run the integration tests (downloads real decks, verifies SHA256 checksums):

```bash
uv run pytest tests/test_integration.py
```

Run everything:

```bash
uv run pytest
```

Skip integration tests (e.g. in CI where network access is unavailable):

```bash
uv run pytest -m "not integration"
```

## Limitations

- Only supports **public** DocSend decks (no email gate or passcode)
- Requires Chromium to be installed via `playwright install chromium`
- S3 signed URLs expire in ~10-15 minutes (handled automatically)

## License

MIT
