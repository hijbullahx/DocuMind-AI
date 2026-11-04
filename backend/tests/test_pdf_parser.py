"""
Unit tests for the Digital PDF Text and Table Extractor (PDFParser).
Uses synthetic in-memory/temp PDFs generated via ReportLab to test:
- Text extraction fidelity
- Multi-page pagination
- Table extraction
- Document metadata
- Blank pages & image-only pages (NEEDS_OCR status)
- Corrupted and empty files
- Mixed document classification (digital + blank, digital + image, digital + image + blank)
"""
import io
import os
import tempfile
from pathlib import Path
import pytest
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

from apps.ingestion.base import ExtractionStatus
from apps.ingestion.pdf_parser import PDFParser


@pytest.fixture
def parser():
    return PDFParser()


def create_sample_invoice_pdf(path: Path) -> Path:
    """Creates a realistic synthetic single-page invoice PDF."""
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setTitle("Invoice INV-2026-001")
    c.setAuthor("DocuMind Financial Systems")

    # Header
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, 750, "INVOICE")
    c.setFont("Helvetica", 10)
    c.drawString(50, 730, "Invoice Number: INV-2026-001")
    c.drawString(50, 715, "Invoice Date: 2026-11-04")
    c.drawString(50, 700, "Supplier: Global Logistics Corp")
    c.drawString(50, 685, "Customer: Acme Enterprise Ltd")

    # Line Item details in text
    c.drawString(50, 650, "Description: Cloud Data Warehousing Service")
    c.drawString(50, 635, "Quantity: 10 | Unit Price: 150.00 | Total: 1500.00")
    c.drawString(50, 600, "Subtotal: $1,500.00")
    c.drawString(50, 585, "Tax (10%): $150.00")
    c.drawString(50, 570, "Total Amount Due: $1,650.00 USD")

    c.showPage()
    c.save()
    return path


def create_multi_page_pdf(path: Path, page_count: int = 3) -> Path:
    """Creates a synthetic multi-page document."""
    c = canvas.Canvas(str(path), pagesize=letter)
    for i in range(1, page_count + 1):
        c.setFont("Helvetica-Bold", 14)
        c.drawString(100, 700, f"Document Section {i}")
        c.setFont("Helvetica", 10)
        c.drawString(100, 670, f"This is page content for page number {i} of {page_count}.")
        c.drawString(100, 650, "Financial data and auditing statements are detailed below.")
        c.showPage()
    c.save()
    return path


def create_table_pdf(path: Path) -> Path:
    """Creates a PDF with a structured table using ReportLab Flowables."""
    doc = SimpleDocTemplate(str(path), pagesize=letter)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Invoice Table Statement", styles["Heading1"]),
        Spacer(1, 20),
    ]

    data = [
        ["Item Description", "Qty", "Unit Price", "Total"],
        ["Server Hosting Standard", "2", "$200.00", "$400.00"],
        ["Database Replication", "1", "$350.00", "$350.00"],
        ["SSL Certificate Multi-Domain", "1", "$75.00", "$75.00"],
    ]

    table = Table(data, colWidths=[200, 60, 80, 80])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.navy),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))

    story.append(table)
    doc.build(story)
    return path


def create_blank_pdf(path: Path) -> Path:
    """Creates a PDF with an empty page (0 text, 0 images)."""
    c = canvas.Canvas(str(path), pagesize=letter)
    c.showPage()
    c.save()
    return path


def create_image_only_pdf(path: Path) -> Path:
    """Creates a synthetic scanned PDF page: contains a raster image and zero digital text."""
    img = Image.new("RGB", (200, 100), color=(240, 240, 240))
    temp_img_path = path.parent / "temp_raster.png"
    img.save(temp_img_path)

    try:
        c = canvas.Canvas(str(path), pagesize=letter)
        c.drawImage(str(temp_img_path), 100, 600, width=200, height=100)
        c.showPage()
        c.save()
    finally:
        if temp_img_path.exists():
            temp_img_path.unlink()
    return path


def create_digital_plus_blank_pdf(path: Path) -> Path:
    """Page 1: Digital text, Page 2: Blank page."""
    c = canvas.Canvas(str(path), pagesize=letter)
    # Page 1: digital text
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, 700, "Invoice Summary Statement Page 1")
    c.setFont("Helvetica", 10)
    c.drawString(100, 680, "Vendor details, total amount due $500, customer name Acme.")
    c.showPage()
    # Page 2: blank
    c.showPage()
    c.save()
    return path


def create_digital_plus_image_pdf(path: Path) -> Path:
    """Page 1: Digital text, Page 2: Raster image (scanned receipt)."""
    img = Image.new("RGB", (200, 100), color=(230, 230, 230))
    temp_img = path.parent / "temp_p2.png"
    img.save(temp_img)

    try:
        c = canvas.Canvas(str(path), pagesize=letter)
        # Page 1: digital text
        c.setFont("Helvetica-Bold", 14)
        c.drawString(100, 700, "Purchase Order Details Page 1")
        c.setFont("Helvetica", 10)
        c.drawString(100, 680, "PO Number 998822, Total Cost 1200 USD.")
        c.showPage()
        # Page 2: image only (scanned receipt)
        c.drawImage(str(temp_img), 100, 500, width=200, height=100)
        c.showPage()
        c.save()
    finally:
        if temp_img.exists():
            temp_img.unlink()
    return path


def create_mixed_three_page_pdf(path: Path) -> Path:
    """Page 1: Digital text, Page 2: Scanned image, Page 3: Completely blank."""
    img = Image.new("RGB", (200, 100), color=(220, 220, 220))
    temp_img = path.parent / "temp_p3.png"
    img.save(temp_img)

    try:
        c = canvas.Canvas(str(path), pagesize=letter)
        # Page 1: Digital text
        c.setFont("Helvetica-Bold", 14)
        c.drawString(100, 700, "Master Service Agreement Section 1")
        c.setFont("Helvetica", 10)
        c.drawString(100, 680, "Terms and conditions are fully outlined in this initial page.")
        c.showPage()
        # Page 2: Scanned receipt image
        c.drawImage(str(temp_img), 100, 500, width=200, height=100)
        c.showPage()
        # Page 3: Blank page
        c.showPage()
        c.save()
    finally:
        if temp_img.exists():
            temp_img.unlink()
    return path


def create_image_plus_blank_pdf(path: Path) -> Path:
    """Page 1: Scanned image (no text), Page 2: Blank page."""
    img = Image.new("RGB", (200, 100), color=(210, 210, 210))
    temp_img = path.parent / "temp_p_img_blank.png"
    img.save(temp_img)

    try:
        c = canvas.Canvas(str(path), pagesize=letter)
        # Page 1: Image only
        c.drawImage(str(temp_img), 100, 500, width=200, height=100)
        c.showPage()
        # Page 2: Blank
        c.showPage()
        c.save()
    finally:
        if temp_img.exists():
            temp_img.unlink()
    return path


class TestPDFParser:
    """Test suite for PDFParser."""

    def test_single_page_invoice_extraction(self, parser, tmp_path):
        pdf_path = create_sample_invoice_pdf(tmp_path / "invoice.pdf")
        result = parser.parse(pdf_path)

        assert result.status == ExtractionStatus.SUCCESS
        assert result.metadata.page_count == 1
        assert "INV-2026-001" in result.full_text
        assert "Global Logistics Corp" in result.full_text
        assert "1,650.00" in result.full_text
        assert len(result.pages) == 1
        assert result.pages[0].page_number == 1
        assert result.pages[0].has_text is True
        assert result.pages[0].is_blank is False
        assert result.pages[0].needs_ocr is False
        assert result.pages[0].word_count > 10
        assert result.processing_time_ms > 0

    def test_multi_page_pagination(self, parser, tmp_path):
        pdf_path = create_multi_page_pdf(tmp_path / "multi_page.pdf", page_count=3)
        result = parser.parse(pdf_path)

        assert result.status == ExtractionStatus.SUCCESS
        assert result.metadata.page_count == 3
        assert len(result.pages) == 3
        for idx, page in enumerate(result.pages, start=1):
            assert page.page_number == idx
            assert f"Document Section {idx}" in page.text
            assert page.has_text is True
            assert page.is_blank is False
            assert page.needs_ocr is False

        assert "--- Page Break ---" in result.full_text

    def test_table_extraction(self, parser, tmp_path):
        pdf_path = create_table_pdf(tmp_path / "table_invoice.pdf")
        result = parser.parse(pdf_path)

        assert result.status == ExtractionStatus.SUCCESS
        assert result.tables_extracted >= 1
        assert result.table_extraction_warning is None
        page_tables = result.pages[0].tables
        assert len(page_tables) >= 1
        first_table = page_tables[0]
        # Check table contents
        headers = [col.strip() for col in first_table[0] if col]
        assert "Item Description" in headers
        assert any("Server Hosting Standard" in str(row) for row in first_table)

    def test_metadata_extraction(self, parser, tmp_path):
        pdf_path = create_sample_invoice_pdf(tmp_path / "meta_invoice.pdf")
        result = parser.parse(pdf_path)

        assert result.metadata.title == "Invoice INV-2026-001"
        assert result.metadata.author == "DocuMind Financial Systems"
        assert result.metadata.is_encrypted is False
        assert result.metadata.file_size_bytes > 0

    def test_blank_page_detection(self, parser, tmp_path):
        pdf_path = create_blank_pdf(tmp_path / "blank.pdf")
        result = parser.parse(pdf_path)

        assert result.status == ExtractionStatus.EMPTY
        assert result.metadata.page_count == 1
        assert result.pages[0].has_text is False
        assert result.pages[0].has_images is False
        assert result.pages[0].is_blank is True
        assert result.pages[0].needs_ocr is False
        assert result.pages[0].word_count == 0
        assert result.full_text == ""

    def test_scanned_image_triggers_needs_ocr(self, parser, tmp_path):
        pdf_path = create_image_only_pdf(tmp_path / "scanned_doc.pdf")
        result = parser.parse(pdf_path)

        # Scanned page has raster image but no vector text -> must NOT be called corrupt
        assert result.status == ExtractionStatus.NEEDS_OCR
        assert result.pages[0].has_images is True
        assert result.pages[0].has_text is False
        assert result.pages[0].is_blank is False
        assert result.pages[0].needs_ocr is True

    def test_corrupted_file_handling(self, parser, tmp_path):
        corrupt_path = tmp_path / "corrupt.pdf"
        corrupt_path.write_bytes(b"%PDF-1.4\nGarbage random broken data truncated without EOF...")
        result = parser.parse(corrupt_path)

        assert result.status == ExtractionStatus.CORRUPTED
        assert result.error_message is not None
        assert "Corrupted or invalid PDF format" in result.error_message or "Error" in result.error_message

    def test_zero_byte_empty_file(self, parser, tmp_path):
        zero_byte_path = tmp_path / "zero.pdf"
        zero_byte_path.write_bytes(b"")
        result = parser.parse(zero_byte_path)

        assert result.status == ExtractionStatus.EMPTY
        assert "empty file" in result.error_message.lower()

    def test_non_existent_file(self, parser, tmp_path):
        missing_path = tmp_path / "does_not_exist.pdf"
        result = parser.parse(missing_path)

        assert result.status == ExtractionStatus.FAILED
        assert "not found" in result.error_message.lower()

    def test_parse_from_raw_bytes(self, parser, tmp_path):
        pdf_path = create_sample_invoice_pdf(tmp_path / "bytes_test.pdf")
        raw_bytes = pdf_path.read_bytes()

        result = parser.parse(raw_bytes, filename="in_memory_invoice.pdf")
        assert result.status == ExtractionStatus.SUCCESS
        assert result.filename == "in_memory_invoice.pdf"
        assert "INV-2026-001" in result.full_text

    # --- New Deterministic Mixed-Page Classification Tests ---

    def test_digital_text_plus_blank_page_returns_success(self, parser, tmp_path):
        """Digital text on page 1 + blank on page 2: extraction is complete, no OCR required -> SUCCESS."""
        pdf_path = create_digital_plus_blank_pdf(tmp_path / "text_plus_blank.pdf")
        result = parser.parse(pdf_path)

        assert result.status == ExtractionStatus.SUCCESS
        assert result.metadata.page_count == 2
        # Page 1: Digital text
        assert result.pages[0].has_text is True
        assert result.pages[0].is_blank is False
        assert result.pages[0].needs_ocr is False
        # Page 2: Blank page must NOT trigger OCR
        assert result.pages[1].has_text is False
        assert result.pages[1].is_blank is True
        assert result.pages[1].needs_ocr is False

    def test_digital_text_plus_scanned_image_returns_partial_success(self, parser, tmp_path):
        """Digital text on page 1 + scanned image on page 2 -> PARTIAL_SUCCESS."""
        pdf_path = create_digital_plus_image_pdf(tmp_path / "text_plus_image.pdf")
        result = parser.parse(pdf_path)

        assert result.status == ExtractionStatus.PARTIAL_SUCCESS
        assert result.metadata.page_count == 2
        # Page 1: Digital text
        assert result.pages[0].has_text is True
        assert result.pages[0].needs_ocr is False
        # Page 2: Image requiring OCR
        assert result.pages[1].has_images is True
        assert result.pages[1].has_text is False
        assert result.pages[1].needs_ocr is True
        assert result.pages[1].is_blank is False

    def test_mixed_three_page_digital_scanned_blank(self, parser, tmp_path):
        """Page 1: Digital text, Page 2: Scanned image, Page 3: Blank page -> PARTIAL_SUCCESS."""
        pdf_path = create_mixed_three_page_pdf(tmp_path / "mixed_three.pdf")
        result = parser.parse(pdf_path)

        assert result.status == ExtractionStatus.PARTIAL_SUCCESS
        assert result.metadata.page_count == 3
        # Page 1
        assert result.pages[0].has_text is True
        assert result.pages[0].needs_ocr is False
        assert result.pages[0].is_blank is False
        # Page 2: Scanned image requires OCR
        assert result.pages[1].has_images is True
        assert result.pages[1].needs_ocr is True
        assert result.pages[1].is_blank is False
        # Page 3: Blank page must not require OCR
        assert result.pages[2].has_text is False
        assert result.pages[2].has_images is False
        assert result.pages[2].is_blank is True
        assert result.pages[2].needs_ocr is False

    def test_scanned_image_plus_blank_page_returns_needs_ocr(self, parser, tmp_path):
        """Page 1: Scanned image, Page 2: Blank page. Zero digital text in document -> NEEDS_OCR."""
        pdf_path = create_image_plus_blank_pdf(tmp_path / "image_plus_blank.pdf")
        result = parser.parse(pdf_path)

        assert result.status == ExtractionStatus.NEEDS_OCR
        assert result.metadata.page_count == 2
        # Page 1 needs OCR
        assert result.pages[0].needs_ocr is True
        # Page 2 is blank, does not need OCR
        assert result.pages[1].is_blank is True
        assert result.pages[1].needs_ocr is False
