"""
Unit and Integration Tests for SpreadsheetParser (XLSX, XLS, CSV).
Verifies:
- Single-sheet and multi-sheet XLSX parsing via openpyxl
- Multi-sheet workbook to PageExtraction 1:1 mapping
- Tabular grid extraction (tables) and Markdown text rendering
- CSV parsing with standard and quoted fields
- Blank sheet detection and blank-only workbook handling
- Corrupted file handling for XLSX and XLS
- 0-byte empty file handling
- Unsupported extension rejection
- In-memory raw bytes parsing
- Legacy XLS parsing via xlrd
"""
import io
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import openpyxl

from apps.ingestion.base import ExtractionStatus
from apps.ingestion.spreadsheet_parser import SpreadsheetParser


def create_sample_xlsx(path: Path) -> Path:
    """Generates a synthetic single-sheet XLSX invoice file."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Invoice_INV_001"

    ws.append(["Invoice Number", "Supplier", "Issue Date", "Total Due"])
    ws.append(["INV-2026-001", "Global Logistics Corp", "2026-11-04", "$1,650.00"])
    ws.append(["INV-2026-002", "Acme Supplies Ltd", "2026-11-05", "$820.50"])

    wb.save(path)
    wb.close()
    return path


def create_multi_sheet_xlsx(path: Path) -> Path:
    """Generates a synthetic multi-sheet XLSX financial workbook."""
    wb = openpyxl.Workbook()

    # Sheet 1: Summary
    ws1 = wb.active
    ws1.title = "Summary"
    ws1.append(["Document Type", "Company", "Fiscal Quarter"])
    ws1.append(["Accounts Payable", "DocuMind Corp", "Q4 2026"])

    # Sheet 2: Line_Items
    ws2 = wb.create_sheet(title="Line_Items")
    ws2.append(["Item ID", "Description", "Quantity", "Unit Price", "Total"])
    ws2.append(["ITM-01", "Database Replication Standard", "2", "350.00", "700.00"])
    ws2.append(["ITM-02", "Cloud Virtual Machines", "5", "120.00", "600.00"])

    wb.save(path)
    wb.close()
    return path


def create_multi_sheet_with_blank_xlsx(path: Path) -> Path:
    """Generates a multi-sheet workbook where Sheet 2 is completely blank."""
    wb = openpyxl.Workbook()

    ws1 = wb.active
    ws1.title = "Active_Sheet_1"
    ws1.append(["Header A", "Header B"])
    ws1.append(["Value 1", "Value 2"])

    ws2 = wb.create_sheet(title="Blank_Sheet_2")
    # Intentionally leave ws2 empty

    ws3 = wb.create_sheet(title="Active_Sheet_3")
    ws3.append(["Summary Field", "Amount"])
    ws3.append(["Grand Total", "$1,300.00"])

    wb.save(path)
    wb.close()
    return path


def create_all_blank_xlsx(path: Path) -> Path:
    """Generates a workbook with 2 empty sheets."""
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Empty_1"
    ws2 = wb.create_sheet(title="Empty_2")
    wb.save(path)
    wb.close()
    return path


class TestSpreadsheetParserXLSX:
    """Tests for XLSX format parsing using openpyxl."""

    def test_single_sheet_invoice(self, tmp_path):
        xlsx_path = create_sample_xlsx(tmp_path / "invoice.xlsx")
        parser = SpreadsheetParser()

        result = parser.parse(xlsx_path)

        assert result.status == ExtractionStatus.SUCCESS
        assert result.file_type == "xlsx"
        assert result.metadata.page_count == 1
        assert "Invoice_INV_001" in result.metadata.title
        assert len(result.pages) == 1

        page = result.pages[0]
        assert page.page_number == 1
        assert page.has_text is True
        assert page.is_blank is False
        assert page.needs_ocr is False
        assert page.ocr_applied is False
        assert len(page.tables) == 1

        # Check extracted table data
        table = page.tables[0]
        assert len(table) == 3
        assert table[0] == ["Invoice Number", "Supplier", "Issue Date", "Total Due"]
        assert table[1][0] == "INV-2026-001"
        assert table[1][1] == "Global Logistics Corp"

        # Check Markdown rendered text
        assert "| Invoice Number | Supplier | Issue Date | Total Due |" in page.text
        assert "INV-2026-001" in result.full_text
        assert "Global Logistics Corp" in result.full_text
        assert result.tables_extracted == 1
        assert result.processing_time_ms > 0

    def test_multi_sheet_workbook(self, tmp_path):
        xlsx_path = create_multi_sheet_xlsx(tmp_path / "multi_sheet.xlsx")
        parser = SpreadsheetParser()

        result = parser.parse(xlsx_path)

        assert result.status == ExtractionStatus.SUCCESS
        assert result.metadata.page_count == 2
        assert len(result.pages) == 2
        assert "Summary" in result.metadata.title
        assert "Line_Items" in result.metadata.title

        # Page 1: Summary
        p1 = result.pages[0]
        assert p1.page_number == 1
        assert p1.has_text is True
        assert p1.is_blank is False
        assert "Accounts Payable" in p1.text

        # Page 2: Line Items
        p2 = result.pages[1]
        assert p2.page_number == 2
        assert p2.has_text is True
        assert p2.is_blank is False
        assert "Database Replication Standard" in p2.text

        assert result.tables_extracted == 2
        assert "--- Page Break ---" in result.full_text

    def test_multi_sheet_with_blank_sheet(self, tmp_path):
        xlsx_path = create_multi_sheet_with_blank_xlsx(tmp_path / "with_blank.xlsx")
        parser = SpreadsheetParser()

        result = parser.parse(xlsx_path)

        assert result.status == ExtractionStatus.SUCCESS
        assert result.metadata.page_count == 3
        assert len(result.pages) == 3

        # Sheet 1: Active
        assert result.pages[0].has_text is True
        assert result.pages[0].is_blank is False

        # Sheet 2: Blank
        assert result.pages[1].has_text is False
        assert result.pages[1].is_blank is True
        assert result.pages[1].tables == []
        assert result.pages[1].text == ""

        # Sheet 3: Active
        assert result.pages[2].has_text is True
        assert result.pages[2].is_blank is False

        assert result.tables_extracted == 2

    def test_all_blank_sheets_returns_empty(self, tmp_path):
        xlsx_path = create_all_blank_xlsx(tmp_path / "all_blank.xlsx")
        parser = SpreadsheetParser()

        result = parser.parse(xlsx_path)

        assert result.status == ExtractionStatus.EMPTY
        assert result.metadata.page_count == 2
        assert all(p.is_blank is True for p in result.pages)
        assert result.tables_extracted == 0
        assert result.full_text == ""

    def test_corrupted_xlsx_file(self, tmp_path):
        corrupt_path = tmp_path / "corrupt.xlsx"
        corrupt_path.write_bytes(b"PK\x03\x04BrokenNotAZipFileContentRandomData")
        parser = SpreadsheetParser()

        result = parser.parse(corrupt_path)

        assert result.status == ExtractionStatus.CORRUPTED
        assert "corrupted" in result.error_message.lower() or "invalid" in result.error_message.lower()

    def test_zero_byte_xlsx(self, tmp_path):
        zero_path = tmp_path / "zero.xlsx"
        zero_path.write_bytes(b"")
        parser = SpreadsheetParser()

        result = parser.parse(zero_path)

        assert result.status == ExtractionStatus.EMPTY
        assert "empty file" in result.error_message.lower()


class TestSpreadsheetParserCSV:
    """Tests for CSV parsing."""

    def test_csv_standard_invoice(self, tmp_path):
        csv_path = tmp_path / "test_invoice.csv"
        csv_path.write_text(
            'Invoice Number,Supplier,Date,Total Amount\n'
            'INV-9901,Apex Tech Corp,2026-11-04,"$1,250.00"\n'
            'INV-9902,Nova Logistics,2026-11-05,"$3,400.00"\n',
            encoding="utf-8"
        )
        parser = SpreadsheetParser()

        result = parser.parse(csv_path)

        assert result.status == ExtractionStatus.SUCCESS
        assert result.file_type == "csv"
        assert result.metadata.page_count == 1
        assert len(result.pages) == 1

        page = result.pages[0]
        assert page.page_number == 1
        assert page.has_text is True
        assert page.is_blank is False
        assert len(page.tables) == 1

        table = page.tables[0]
        assert len(table) == 3
        assert table[0] == ["Invoice Number", "Supplier", "Date", "Total Amount"]
        assert table[1][0] == "INV-9901"
        assert "Apex Tech Corp" in result.full_text
        assert "$1,250.00" in result.full_text

    def test_csv_empty_content_returns_empty(self, tmp_path):
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text(",,,\n,,,\n\n", encoding="utf-8")
        parser = SpreadsheetParser()

        result = parser.parse(csv_path)

        assert result.status == ExtractionStatus.EMPTY
        assert result.pages[0].is_blank is True
        assert result.tables_extracted == 0

    def test_zero_byte_csv(self, tmp_path):
        zero_path = tmp_path / "zero.csv"
        zero_path.write_bytes(b"")
        parser = SpreadsheetParser()

        result = parser.parse(zero_path)

        assert result.status == ExtractionStatus.EMPTY
        assert "empty" in result.error_message.lower()


class TestSpreadsheetParserLegacyXLS:
    """Tests for legacy XLS binary format."""

    def test_corrupted_xls_returns_corrupted(self, tmp_path):
        corrupt_path = tmp_path / "corrupt.xls"
        corrupt_path.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1BrokenOLEHeader")
        parser = SpreadsheetParser()

        result = parser.parse(corrupt_path)

        assert result.status == ExtractionStatus.CORRUPTED
        assert "corrupted" in result.error_message.lower() or "invalid" in result.error_message.lower()

    @patch("xlrd.open_workbook")
    def test_valid_xls_parsed_via_mock(self, mock_open_wb, tmp_path):
        """Simulates legacy BIFF8 XLS workbook parsing via xlrd."""
        mock_sheet = MagicMock()
        mock_sheet.nrows = 2
        mock_sheet.ncols = 3
        mock_sheet.cell_value.side_effect = lambda r, c: [
            ["Item", "Quantity", "Price"],
            ["Server License", "1", "499.00"]
        ][r][c]

        mock_wb = MagicMock()
        mock_wb.sheet_names.return_value = ["LegacySheet1"]
        mock_wb.sheet_by_name.return_value = mock_sheet
        mock_open_wb.return_value = mock_wb

        xls_path = tmp_path / "mock.xls"
        xls_path.write_bytes(b"Simulated_XLS_Bytes")

        parser = SpreadsheetParser()
        result = parser.parse(xls_path)

        assert result.status == ExtractionStatus.SUCCESS
        assert result.file_type == "xls"
        assert result.metadata.page_count == 1
        assert len(result.pages) == 1
        assert "Server License" in result.full_text
        assert len(result.pages[0].tables) == 1


class TestSpreadsheetParserGeneral:
    """Tests for input handling, in-memory bytes, and unsupported extensions."""

    def test_in_memory_bytes_parsing(self, tmp_path):
        xlsx_path = create_sample_xlsx(tmp_path / "in_mem.xlsx")
        file_bytes = xlsx_path.read_bytes()

        parser = SpreadsheetParser()
        result = parser.parse(file_bytes, filename="in_memory_invoice.xlsx")

        assert result.status == ExtractionStatus.SUCCESS
        assert result.filename == "in_memory_invoice.xlsx"
        assert result.file_type == "xlsx"
        assert "INV-2026-001" in result.full_text

    def test_unsupported_extension_rejection(self, tmp_path):
        bad_file = tmp_path / "test.pdf"
        bad_file.write_bytes(b"%PDF-1.4 header")
        parser = SpreadsheetParser()

        result = parser.parse(bad_file)

        assert result.status == ExtractionStatus.FAILED
        assert "Unsupported spreadsheet file extension" in result.error_message
        assert ".pdf" in result.error_message

    def test_file_not_found(self, tmp_path):
        missing_file = tmp_path / "non_existent.xlsx"
        parser = SpreadsheetParser()

        result = parser.parse(missing_file)

        assert result.status == ExtractionStatus.FAILED
        assert "not found" in result.error_message.lower()
