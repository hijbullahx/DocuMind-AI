"""
Unit and Integration Tests for DocumentIngestionService and Corrupted File Guard.
Verifies:
- Unified entry point routing across PDF, Images, Spreadsheets, and CSV
- Magic byte detection when extension is missing or generic (.bin, .dat)
- Corrupted file guard for malformed PDF, XLSX, and Image containers
- Zero-byte empty file detection
- Unsupported file format rejection (.exe, .docx, .mp3, etc.)
- Missing file error handling
- Unhandled parser exception isolation
- Custom OCR engine propagation
"""
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from PIL import Image, ImageDraw
import openpyxl
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from apps.ingestion.base import ExtractionStatus
from apps.ingestion.ingestion_service import DocumentIngestionService
from apps.ingestion.ocr_engine import MockOCREngine


def create_sample_pdf(path: Path) -> Path:
    """Creates a valid PDF invoice."""
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, 700, "INVOICE #PDF-SERVICE-001")
    c.setFont("Helvetica", 10)
    c.drawString(100, 680, "Supplier: Apex Systems Inc Total: $1,250.00")
    c.showPage()
    c.save()
    return path


def create_sample_png(path: Path) -> Path:
    """Creates a valid synthetic PNG image with high-contrast text."""
    img = Image.new("RGB", (300, 100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 30), "RECEIPT #PNG-SERVICE-002", fill=(0, 0, 0))
    img.save(path)
    return path


def create_sample_xlsx(path: Path) -> Path:
    """Creates a valid synthetic XLSX spreadsheet."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Invoices"
    ws.append(["Invoice Number", "Client", "Total"])
    ws.append(["INV-XLSX-003", "Nova Corp", "$3,500.00"])
    wb.save(path)
    wb.close()
    return path


def create_sample_csv(path: Path) -> Path:
    """Creates a valid synthetic CSV file."""
    path.write_text(
        "Invoice Number,Vendor,Total\n"
        "INV-CSV-004,Zenith Logistics,\"$4,200.00\"\n",
        encoding="utf-8"
    )
    return path


@pytest.fixture
def service():
    """Provides a DocumentIngestionService configured with MockOCREngine."""
    mock_ocr = MockOCREngine(canned_text="RECEIPT #PNG-SERVICE-002 $99.00", confidence=0.95)
    return DocumentIngestionService(ocr_engine=mock_ocr)


class TestDocumentIngestionServiceRouting:
    """Tests unified routing to PDF, Image, and Spreadsheet parsers."""

    def test_ingest_pdf(self, service, tmp_path):
        pdf_path = create_sample_pdf(tmp_path / "invoice.pdf")
        result = service.ingest(pdf_path)

        assert result.status == ExtractionStatus.SUCCESS
        assert result.file_type == "pdf"
        assert result.metadata.page_count == 1
        assert "INVOICE #PDF-SERVICE-001" in result.full_text
        assert result.metadata.file_size_bytes > 0

    def test_ingest_image_png(self, service, tmp_path):
        png_path = create_sample_png(tmp_path / "receipt.png")
        result = service.ingest(png_path)

        assert result.status == ExtractionStatus.SUCCESS
        assert result.file_type == "png"
        assert result.metadata.page_count == 1
        assert "RECEIPT #PNG-SERVICE-002" in result.full_text
        assert result.pages[0].ocr_applied is True

    def test_ingest_spreadsheet_xlsx(self, service, tmp_path):
        xlsx_path = create_sample_xlsx(tmp_path / "financials.xlsx")
        result = service.ingest(xlsx_path)

        assert result.status == ExtractionStatus.SUCCESS
        assert result.file_type == "xlsx"
        assert result.metadata.page_count == 1
        assert "INV-XLSX-003" in result.full_text
        assert result.tables_extracted == 1

    def test_ingest_csv(self, service, tmp_path):
        csv_path = create_sample_csv(tmp_path / "statement.csv")
        result = service.ingest(csv_path)

        assert result.status == ExtractionStatus.SUCCESS
        assert result.file_type == "csv"
        assert result.metadata.page_count == 1
        assert "INV-CSV-004" in result.full_text
        assert result.tables_extracted == 1

    @patch("xlrd.open_workbook")
    def test_ingest_legacy_xls(self, mock_open_wb, service, tmp_path):
        """Simulates legacy XLS parsing routed through unified service."""
        mock_sheet = MagicMock()
        mock_sheet.nrows = 2
        mock_sheet.ncols = 3
        mock_sheet.cell_value.side_effect = lambda r, c: [
            ["Invoice #", "Vendor", "Total"],
            ["INV-XLS-005", "Apex Corp", "750.00"]
        ][r][c]

        mock_wb = MagicMock()
        mock_wb.sheet_names.return_value = ["Sheet1"]
        mock_wb.sheet_by_name.return_value = mock_sheet
        mock_open_wb.return_value = mock_wb

        xls_path = tmp_path / "mock.xls"
        xls_path.write_bytes(b"Simulated_XLS_Bytes")

        result = service.ingest(xls_path)
        assert result.status == ExtractionStatus.SUCCESS
        assert result.file_type == "xls"
        assert result.metadata.page_count == 1
        assert "INV-XLS-005" in result.full_text

    def test_ingest_in_memory_bytes(self, service, tmp_path):
        pdf_path = create_sample_pdf(tmp_path / "in_mem.pdf")
        pdf_bytes = pdf_path.read_bytes()

        result = service.ingest(pdf_bytes, filename="in_memory_invoice.pdf")

        assert result.status == ExtractionStatus.SUCCESS
        assert result.filename == "in_memory_invoice.pdf"
        assert result.file_type == "pdf"
        assert "INVOICE #PDF-SERVICE-001" in result.full_text


class TestMagicByteSniffing:
    """Tests format sniffing when filename has generic or missing extension."""

    def test_sniff_pdf_without_extension(self, service, tmp_path):
        pdf_path = create_sample_pdf(tmp_path / "temp.pdf")
        pdf_bytes = pdf_path.read_bytes()

        # Name file with generic .bin extension
        result = service.ingest(pdf_bytes, filename="upload_generic.bin")

        assert result.status == ExtractionStatus.SUCCESS
        assert result.file_type == "pdf"
        assert "INVOICE #PDF-SERVICE-001" in result.full_text

    def test_sniff_png_without_extension(self, service, tmp_path):
        png_path = create_sample_png(tmp_path / "temp.png")
        png_bytes = png_path.read_bytes()

        result = service.ingest(png_bytes, filename="scanned_photo.dat")

        assert result.status == ExtractionStatus.SUCCESS
        assert result.file_type == "png"
        assert result.pages[0].ocr_applied is True

    def test_sniff_xlsx_without_extension(self, service, tmp_path):
        xlsx_path = create_sample_xlsx(tmp_path / "temp.xlsx")
        xlsx_bytes = xlsx_path.read_bytes()

        result = service.ingest(xlsx_bytes, filename="ledger_blob")

        assert result.status == ExtractionStatus.SUCCESS
        assert result.file_type == "xlsx"
        assert "INV-XLSX-003" in result.full_text


class TestCorruptedFileGuard:
    """Tests safe error isolation and corruption guarding."""

    def test_zero_byte_file_from_path(self, service, tmp_path):
        zero_file = tmp_path / "empty.pdf"
        zero_file.write_bytes(b"")

        result = service.ingest(zero_file)

        assert result.status == ExtractionStatus.EMPTY
        assert "empty (0 bytes)" in result.error_message.lower()
        assert result.metadata.file_size_bytes == 0

    def test_zero_byte_bytes_input(self, service):
        result = service.ingest(b"", filename="empty_upload.xlsx")

        assert result.status == ExtractionStatus.EMPTY
        assert "empty (0 bytes)" in result.error_message.lower()

    def test_non_existent_file(self, service, tmp_path):
        missing = tmp_path / "non_existent_doc.pdf"

        result = service.ingest(missing)

        assert result.status == ExtractionStatus.FAILED
        assert "not found" in result.error_message.lower()

    def test_corrupted_pdf_file(self, service, tmp_path):
        corrupt = tmp_path / "corrupt.pdf"
        corrupt.write_bytes(b"%PDF-1.4\nBrokenTruncatedCorruptDataWithoutEOF")

        result = service.ingest(corrupt)

        assert result.status == ExtractionStatus.CORRUPTED
        assert "corrupted" in result.error_message.lower() or "error" in result.error_message.lower()

    def test_corrupted_xlsx_file(self, service, tmp_path):
        corrupt = tmp_path / "corrupt.xlsx"
        corrupt.write_bytes(b"PK\x03\x04RandomNotAZipArchiveContent")

        result = service.ingest(corrupt)

        assert result.status == ExtractionStatus.CORRUPTED
        assert "corrupted" in result.error_message.lower() or "invalid" in result.error_message.lower()

    def test_corrupted_xls_file(self, service, tmp_path):
        corrupt = tmp_path / "corrupt.xls"
        corrupt.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1BrokenCompDocPayload")

        result = service.ingest(corrupt)

        assert result.status == ExtractionStatus.CORRUPTED
        assert "corrupted" in result.error_message.lower() or "invalid" in result.error_message.lower()

    def test_corrupted_image_file(self, service, tmp_path):
        corrupt = tmp_path / "corrupt.png"
        corrupt.write_bytes(b"NotAPNGImageHeader")

        result = service.ingest(corrupt)

        assert result.status == ExtractionStatus.CORRUPTED

    def test_unsupported_file_extension(self, service, tmp_path):
        exe_file = tmp_path / "malicious.exe"
        exe_file.write_bytes(b"MZ\x90\x00BinaryExecutableContent")

        result = service.ingest(exe_file)

        assert result.status == ExtractionStatus.FAILED
        assert "unsupported document format" in result.error_message.lower()
        assert ".exe" in result.error_message.lower()

    def test_unhandled_parser_exception_isolation(self, service):
        """Simulates an unexpected runtime crash inside a subparser."""
        mock_pdf_parser = MagicMock()
        mock_pdf_parser.parse.side_effect = RuntimeError("Fatal PyMuPDF C++ Segfault")

        isolated_service = DocumentIngestionService(pdf_parser=mock_pdf_parser)
        result = isolated_service.ingest(b"%PDF-1.5 fake valid header", filename="test.pdf")

        # Must catch exception and report FAILED without crashing the caller
        assert result.status == ExtractionStatus.FAILED
        assert "Unhandled parser exception" in result.error_message
        assert "Fatal PyMuPDF C++ Segfault" in result.error_message
        assert result.processing_time_ms > 0
