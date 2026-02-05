# docsend-dl

**Save any public DocSend deck as a PDF — one command, full quality.**

[![PyPI version](https://img.shields.io/pypi/v/docsend-dl)](https://pypi.org/project/docsend-dl/)
[![Python versions](https://img.shields.io/pypi/pyversions/docsend-dl)](https://pypi.org/project/docsend-dl/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Quickstart

```bash
pip install docsend-dl && playwright install chromium
docsend-dl https://docsend.com/view/XXXXXX
```

That's it. You'll get a PDF named after the deck in your current directory.

## Demo

```
$ docsend-dl https://dbx.docsend.com/view/n43v89r
Found deck: "docsend-n43v89r" (21 slides)
Got 21/21 image URLs
  Downloading slides ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 21/21 0:00:00
╭──────────────────────── Done in 32.2s ─────────────────────────╮
│ Slides saved: 21/21                                            │
│ PDF size: 9.5 MB                                               │
│ Output: /home/user/docsend-n43v89r.pdf                         │
╰────────────────────────────────────────────────────────────────╯
```

## Features

- **PDF by default** — slides are assembled into a single PDF at full resolution with no re-encoding
- **PNG export** — pass `--images` to save individual slide images instead
- **Smart output paths** — pass a `.pdf` filename, a directory, or let it default to `{deck title}.pdf`
- **Fast** — downloads all slides in parallel with automatic retries
- **Works with both** `docsend.com` and `dbx.docsend.com` URLs
- **Headless** — runs in the background by default; use `--no-headless` to watch the browser

## Installation

You need the package itself plus a Chromium browser for Playwright:

```bash
pip install docsend-dl
playwright install chromium
```

Or if you use [uv](https://docs.astral.sh/uv/):

```bash
uv tool install docsend-dl
uv run playwright install chromium
```

## Usage

### CLI

```bash
# Download as PDF (default)
docsend-dl https://docsend.com/view/XXXXXX

# Save PDF to a specific path
docsend-dl https://docsend.com/view/XXXXXX --output "My Deck.pdf"

# Save PDF into a directory (uses deck title as filename)
docsend-dl https://docsend.com/view/XXXXXX --output ./downloads

# Download as individual PNG images instead
docsend-dl https://docsend.com/view/XXXXXX --images

# Show the browser window during download
docsend-dl https://dbx.docsend.com/view/XXXXXX --no-headless
```

### Python API

```python
import asyncio
from docsend_dl import download_deck

# Download as PDF (default)
result = asyncio.run(download_deck(
    url="https://docsend.com/view/XXXXXX",
))
print(f"Saved PDF to {result.output_path} ({result.total_bytes} bytes)")

# Download as individual images
result = asyncio.run(download_deck(
    url="https://docsend.com/view/XXXXXX",
    output="My Deck",
    images_only=True,
))
print(f"Saved {result.successes}/{result.slide_count} slides")
```

For finer control you can call the extraction and download steps separately:

```python
import asyncio
from pathlib import Path
from docsend_dl import extract_slide_urls, download_slides

async def main():
    deck_info = await extract_slide_urls(url="https://docsend.com/view/XXXXXX")
    result = await download_slides(
        urls=deck_info.image_urls,
        output_dir=Path("slides"),
    )
    print(f"Downloaded {result.successes} slides")

asyncio.run(main())
```

## How It Works

1. Opens the DocSend page in a headless Chromium browser (via [Playwright](https://playwright.dev/python/))
2. Extracts each slide's image URL from the page data
3. Downloads all slide images in parallel (via [httpx](https://www.python-httpx.org/))
4. Assembles the images into a single PDF (via [img2pdf](https://pypi.org/project/img2pdf/)) or saves them as PNGs

## Limitations

- Only works with **public** decks — email-gated and passcode-protected decks are not supported
- Requires Chromium to be installed via `playwright install chromium`

## Contributing

```bash
# Clone and install dev dependencies
git clone https://github.com/captivus/docsend-dl.git
cd docsend-dl
uv sync

# Run unit tests (fast, no network needed)
uv run pytest -m "not integration"

# Run integration tests (downloads real decks, verifies checksums)
uv run pytest tests/test_integration.py

# Run everything
uv run pytest
```

Bug reports and pull requests are welcome on [GitHub](https://github.com/captivus/docsend-dl/issues).

## License

[MIT](LICENSE)
