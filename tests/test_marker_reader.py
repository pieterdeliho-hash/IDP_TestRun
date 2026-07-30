"""Tests for the Marker reader."""

from pathlib import Path

import pytest

from src.marker_reader import MarkerReader


@pytest.fixture
def reader() -> MarkerReader:
    return MarkerReader()


class TestMarkerReader:
    def test_file_not_found(self, reader: MarkerReader) -> None:
        with pytest.raises(FileNotFoundError):
            reader.read("nonexistent.pdf")

    def test_non_pdf_raises(self, reader: MarkerReader, tmp_path: Path) -> None:
        fake = tmp_path / "file.txt"
        fake.write_text("hello")
        with pytest.raises(ValueError, match="Expected a .pdf"):
            reader.read(fake)
