"""Unit tests for PDF assembly — no network required."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pytest

from docsend_dl.assembler import assemble_pdf


def _create_minimal_png(path: Path, *, width: int = 100, height: int = 100) -> None:
    """Create a minimal valid PNG file for testing."""

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr = _chunk(b"IHDR", ihdr_data)

    raw_data = b""
    for _ in range(height):
        raw_data += b"\x00" + b"\xff\x00\x00" * width
    idat = _chunk(b"IDAT", zlib.compress(raw_data))
    iend = _chunk(b"IEND", b"")

    path.write_bytes(signature + ihdr + idat + iend)


class TestAssemblePdf:
    def test_single_image(self, tmp_path: Path):
        img = tmp_path / "slide_01.png"
        _create_minimal_png(path=img)
        out = tmp_path / "output.pdf"

        size = assemble_pdf(image_paths=[img], output_path=out)

        assert out.exists()
        assert size > 0
        assert out.read_bytes()[:5] == b"%PDF-"

    def test_multiple_images(self, tmp_path: Path):
        images = []
        for i in range(3):
            img = tmp_path / f"slide_{i + 1:02d}.png"
            _create_minimal_png(path=img)
            images.append(img)
        out = tmp_path / "output.pdf"

        size = assemble_pdf(image_paths=images, output_path=out)

        assert out.exists()
        assert size > 0
        assert out.read_bytes()[:5] == b"%PDF-"

    def test_creates_parent_directories(self, tmp_path: Path):
        img = tmp_path / "slide_01.png"
        _create_minimal_png(path=img)
        out = tmp_path / "nested" / "deep" / "output.pdf"

        assemble_pdf(image_paths=[img], output_path=out)

        assert out.exists()

    def test_empty_image_list_raises(self, tmp_path: Path):
        out = tmp_path / "output.pdf"

        with pytest.raises(ValueError, match="must not be empty"):
            assemble_pdf(image_paths=[], output_path=out)

    def test_missing_image_raises(self, tmp_path: Path):
        out = tmp_path / "output.pdf"
        missing = tmp_path / "nonexistent.png"

        with pytest.raises(FileNotFoundError):
            assemble_pdf(image_paths=[missing], output_path=out)
