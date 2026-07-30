"""Tests for the PDF reader module."""

from pathlib import Path

import pytest

from src.document_reader import PDFReader


@pytest.fixture
def reader() -> PDFReader:
    return PDFReader()


class TestPDFReader:
    def test_file_not_found(self, reader: PDFReader) -> None:
        with pytest.raises(FileNotFoundError):
            reader.read("nonexistent.pdf")

    def test_non_pdf_raises(self, reader: PDFReader, tmp_path: Path) -> None:
        fake = tmp_path / "file.txt"
        fake.write_text("hello")
        with pytest.raises(ValueError, match="Expected a .pdf"):
            reader.read(fake)

    def test_ocr_lang_parameter(self, tmp_path: Path) -> None:
        reader = PDFReader(ocr_lang="fra")
        with pytest.raises(FileNotFoundError):
            reader.read("nonexistent.pdf")


class TestPyMuPDFReader:
    def test_file_not_found(self) -> None:
        from src.pymupdf_reader import PyMuPDFReader

        with pytest.raises(FileNotFoundError):
            PyMuPDFReader().read("nonexistent.pdf")

    def test_non_pdf_raises(self, tmp_path: Path) -> None:
        from src.pymupdf_reader import PyMuPDFReader

        fake = tmp_path / "file.txt"
        fake.write_text("hello")
        with pytest.raises(ValueError, match="Expected a .pdf"):
            PyMuPDFReader().read(fake)


class TestPdfPlumberReader:
    def test_file_not_found(self) -> None:
        from src.pdfplumber_reader import PdfPlumberReader

        with pytest.raises(FileNotFoundError):
            PdfPlumberReader().read("nonexistent.pdf")

    def test_non_pdf_raises(self, tmp_path: Path) -> None:
        from src.pdfplumber_reader import PdfPlumberReader

        fake = tmp_path / "file.txt"
        fake.write_text("hello")
        with pytest.raises(ValueError, match="Expected a .pdf"):
            PdfPlumberReader().read(fake)


class TestDoclingReader:
    def test_file_not_found(self) -> None:
        from src.docling_reader import DoclingReader

        with pytest.raises(FileNotFoundError):
            DoclingReader().read("nonexistent.pdf")

    def test_non_pdf_raises(self, tmp_path: Path) -> None:
        from src.docling_reader import DoclingReader

        fake = tmp_path / "file.txt"
        fake.write_text("hello")
        with pytest.raises(ValueError, match="Expected a .pdf"):
            DoclingReader().read(fake)


class TestUnstructuredReader:
    def test_file_not_found(self) -> None:
        from src.unstructured_reader import UnstructuredReader

        with pytest.raises(FileNotFoundError):
            UnstructuredReader().read("nonexistent.pdf")

    def test_non_pdf_raises(self, tmp_path: Path) -> None:
        from src.unstructured_reader import UnstructuredReader

        fake = tmp_path / "file.txt"
        fake.write_text("hello")
        with pytest.raises(ValueError, match="Expected a .pdf"):
            UnstructuredReader().read(fake)
