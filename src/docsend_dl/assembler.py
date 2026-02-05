"""Assemble downloaded slide images into a single PDF file."""

from __future__ import annotations

from pathlib import Path

import img2pdf


def assemble_pdf(*, image_paths: list[Path], output_path: Path) -> int:
    """Combine slide images into a single PDF file.

    Args:
        image_paths: Ordered list of slide image file paths.
        output_path: Path to write the output PDF.

    Returns:
        Size of the written PDF in bytes.

    Raises:
        ValueError: If *image_paths* is empty.
        FileNotFoundError: If any image path does not exist.
    """
    if not image_paths:
        raise ValueError("image_paths must not be empty")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    for p in image_paths:
        if not p.exists():
            raise FileNotFoundError(f"Image not found: {p}")

    pdf_bytes = img2pdf.convert([p.read_bytes() for p in image_paths])
    output_path.write_bytes(pdf_bytes)

    return len(pdf_bytes)
