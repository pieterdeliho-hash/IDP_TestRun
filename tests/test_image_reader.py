"""Tests for the image reader."""

from pathlib import Path

import pytest

from src.image_reader import ImageReader


@pytest.fixture
def reader() -> ImageReader:
    return ImageReader()


class TestImageReader:
    def test_file_not_found(self, reader: ImageReader) -> None:
        with pytest.raises(FileNotFoundError):
            reader.read("nonexistent.png")

    def test_unsupported_extension(self, reader: ImageReader, tmp_path: Path) -> None:
        fake = tmp_path / "file.txt"
        fake.write_text("hello")
        with pytest.raises(ValueError, match="Unsupported extension"):
            reader.read(fake)

    def test_unknown_backend(self, tmp_path: Path) -> None:
        fake = tmp_path / "test.png"
        fake.write_bytes(b"\x89PNG\r\n\x1a\n")  # minimal PNG header
        reader = ImageReader(backend="nonexistent")
        with pytest.raises(ValueError, match="Unknown backend"):
            reader.read(fake)
