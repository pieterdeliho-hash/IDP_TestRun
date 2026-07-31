"""Tests for utils module."""

from pathlib import Path

import pytest

from src.utils import (
    ReaderProtocol,
    batch_read,
    find_pdfs,
    validate_pdf_path,
)


class TestValidatePdfPath:
    def test_valid_path(self, tmp_path: Path) -> None:
        pdf = tmp_path / "test.pdf"
        pdf.touch()
        result = validate_pdf_path(pdf)
        assert result == pdf

    def test_string_path(self, tmp_path: Path) -> None:
        pdf = tmp_path / "test.pdf"
        pdf.touch()
        result = validate_pdf_path(str(pdf))
        assert result == pdf

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError, match="File not found"):
            validate_pdf_path("nonexistent.pdf")

    def test_not_pdf(self, tmp_path: Path) -> None:
        fake = tmp_path / "file.txt"
        fake.write_text("hello")
        with pytest.raises(ValueError, match="Expected a .pdf"):
            validate_pdf_path(fake)

    def test_uppercase_extension(self, tmp_path: Path) -> None:
        pdf = tmp_path / "test.PDF"
        pdf.touch()
        result = validate_pdf_path(pdf)
        assert result == pdf


class TestFindPdfs:
    def test_empty_directory(self, tmp_path: Path) -> None:
        result = find_pdfs(tmp_path)
        assert result == []

    def test_finds_pdfs(self, tmp_path: Path) -> None:
        (tmp_path / "a.pdf").touch()
        (tmp_path / "b.pdf").touch()
        (tmp_path / "c.txt").touch()
        result = find_pdfs(tmp_path)
        assert len(result) == 2
        assert result[0].name == "a.pdf"
        assert result[1].name == "b.pdf"

    def test_recursive(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "a.pdf").touch()
        (sub / "b.pdf").touch()
        result = find_pdfs(tmp_path, recursive=True)
        assert len(result) == 2

    def test_non_recursive(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "a.pdf").touch()
        (sub / "b.pdf").touch()
        result = find_pdfs(tmp_path, recursive=False)
        assert len(result) == 1
        assert result[0].name == "a.pdf"

    def test_case_insensitive(self, tmp_path: Path) -> None:
        (tmp_path / "a.pdf").touch()
        (tmp_path / "b.PDF").touch()
        (tmp_path / "c.Pdf").touch()
        result = find_pdfs(tmp_path)
        assert len(result) == 3

    def test_sorted_by_name(self, tmp_path: Path) -> None:
        (tmp_path / "c.pdf").touch()
        (tmp_path / "a.pdf").touch()
        (tmp_path / "b.pdf").touch()
        result = find_pdfs(tmp_path)
        names = [p.name for p in result]
        assert names == ["a.pdf", "b.pdf", "c.pdf"]


class TestReaderProtocol:
    def test_protocol_conformance(self) -> None:
        """All reader classes conform to ReaderProtocol."""
        from src.docling_reader import DoclingReader
        from src.document_reader import PDFReader
        from src.hybrid_reader import HybridReader
        from src.image_reader import ImageReader
        from src.marker_reader import MarkerReader
        from src.pdfplumber_reader import PdfPlumberReader
        from src.pymupdf_reader import PyMuPDFReader
        from src.surya_reader import SuryaReader
        from src.unstructured_reader import UnstructuredReader

        # Static check: these assignments are valid because each class
        # implements read(file_path: str | Path, *, use_ocr: bool = True) -> str.
        readers: list[ReaderProtocol] = [
            PDFReader(),
            PyMuPDFReader(),
            PdfPlumberReader(),
            DoclingReader(),
            UnstructuredReader(),
            HybridReader(),
            SuryaReader(),
            MarkerReader(),
            ImageReader(),
        ]
        assert len(readers) == 9


class TestBatchRead:
    def test_empty_directory(self, tmp_path: Path) -> None:
        result = batch_read(tmp_path)
        assert result == {}

    def test_error_reporting(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """batch_read reports errors to stderr."""
        (tmp_path / "bad.pdf").touch()  # empty file, not a real PDF
        batch_read(tmp_path)
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "failed" in captured.err
