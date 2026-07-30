"""Tests for the hybrid PDF reader."""

from pathlib import Path

import pytest

from src.hybrid_reader import HybridReader


@pytest.fixture
def reader() -> HybridReader:
    return HybridReader()


class TestHybridReader:
    def test_file_not_found(self, reader: HybridReader) -> None:
        with pytest.raises(FileNotFoundError):
            reader.read("nonexistent.pdf")

    def test_non_pdf_raises(self, reader: HybridReader, tmp_path: Path) -> None:
        fake = tmp_path / "file.txt"
        fake.write_text("hello")
        with pytest.raises(ValueError, match="Expected a .pdf"):
            reader.read(fake)

    def test_fallback_threshold_parameter(self) -> None:
        reader = HybridReader(fallback_chars_per_page=500)
        assert reader._fallback_chars_per_page == 500
