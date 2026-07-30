"""Tests for the Surya OCR reader."""

from pathlib import Path

import pytest

from src.surya_reader import SuryaReader


@pytest.fixture
def reader() -> SuryaReader:
    return SuryaReader()


class TestSuryaReader:
    def test_file_not_found(self, reader: SuryaReader) -> None:
        with pytest.raises(FileNotFoundError):
            reader.read("nonexistent.pdf")

    def test_non_pdf_raises(self, reader: SuryaReader, tmp_path: Path) -> None:
        fake = tmp_path / "file.txt"
        fake.write_text("hello")
        with pytest.raises(ValueError, match="Expected a .pdf"):
            reader.read(fake)
