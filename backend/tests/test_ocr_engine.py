"""
Unit and Integration Tests for Modular OCR Engine and Standalone ImageParser.
Default test suite uses MockOCREngine for 100% offline, deterministic, fast execution.
Real EasyOCR smoke test is strictly opt-in via RUN_REAL_OCR_SMOKE=1.
"""
import io
import os
import socket
import urllib.error
from pathlib import Path
import pytest
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from apps.ingestion.base import ExtractionStatus
from apps.ingestion.ocr_engine import (
    BaseOCREngine,
    EasyOCREngine,
    MockOCREngine,
    OCRResult,
)
from apps.ingestion.image_parser import ImageParser
from apps.ingestion.pdf_parser import PDFParser


def create_synthetic_image(path: Path, text: str = "INVOICE #INV-2026-999") -> Path:
    """Generates a synthetic PNG image with high-contrast printed text."""
    img = Image.new("RGB", (400, 150), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 30), text, fill=(0, 0, 0))
    draw.text((20, 60), "Supplier: Apex Systems Inc", fill=(0, 0, 0))
    draw.text((20, 90), "Amount Due: $1,250.00 USD", fill=(0, 0, 0))
    img.save(path)
    return path


def create_scanned_pdf(path: Path, image_path: Path) -> Path:
    """Creates a PDF containing an embedded raster image and zero vector text."""
    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawImage(str(image_path), 50, 500, width=400, height=150)
    c.showPage()
    c.save()
    return path


def create_mixed_digital_scanned_pdf(path: Path, image_path: Path) -> Path:
    """Page 1: Digital text, Page 2: Embedded scanned image."""
    c = canvas.Canvas(str(path), pagesize=letter)
    # Page 1: Digital text (adequate words >= 5)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 700, "Purchase Agreement Digital Header")
    c.setFont("Helvetica", 10)
    c.drawString(50, 680, "Vendor details and terms of service are outlined digitally.")
    c.showPage()
    # Page 2: Embedded image
    c.drawImage(str(image_path), 50, 500, width=400, height=150)
    c.showPage()
    c.save()
    return path


def create_mixed_three_page_with_blank(path: Path, image_path: Path) -> Path:
    """Page 1: Digital text, Page 2: Embedded image, Page 3: Completely blank."""
    c = canvas.Canvas(str(path), pagesize=letter)
    # Page 1: Digital text (adequate words >= 5)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 700, "Summary Page Digital Text of Invoiced Statement")
    c.setFont("Helvetica", 10)
    c.drawString(50, 680, "Full financial details are presented below.")
    c.showPage()
    # Page 2: Embedded image
    c.drawImage(str(image_path), 50, 500, width=400, height=150)
    c.showPage()
    # Page 3: Blank page
    c.showPage()
    c.save()
    return path


def create_two_page_scanned_pdf(path: Path, image_path: Path) -> Path:
    """Page 1: Embedded scanned image, Page 2: Embedded scanned image."""
    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawImage(str(image_path), 50, 500, width=400, height=150)
    c.showPage()
    c.drawImage(str(image_path), 50, 500, width=400, height=150)
    c.showPage()
    c.save()
    return path


def create_sparse_text_pdf(path: Path, text: str = "Draft Copy") -> Path:
    """Single page with sparse digital text (< 5 words) and zero images."""
    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawString(100, 700, text)
    c.showPage()
    c.save()
    return path


def create_digital_plus_sparse_pdf(path: Path) -> Path:
    """Page 1: Substantive text (>= 5 words), Page 2: Sparse text (< 5 words, no images)."""
    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawString(100, 700, "This is page one containing substantive digital text for processing.")
    c.showPage()
    c.drawString(100, 700, "Draft Copy")
    c.showPage()
    c.save()
    return path


class TestImageParserWithMockOCR:
    """Unit tests for standalone ImageParser with MockOCREngine."""

    def test_image_parser_success(self, tmp_path):
        img_path = create_synthetic_image(tmp_path / "test_invoice.png")
        mock_engine = MockOCREngine(canned_text="INVOICE #999 TOTAL $1250.00", confidence=0.92)
        parser = ImageParser(ocr_engine=mock_engine)

        result = parser.parse(img_path)
        assert result.status == ExtractionStatus.SUCCESS
        assert result.file_type == "png"
        assert result.metadata.page_count == 1
        assert len(result.pages) == 1
        page = result.pages[0]
        assert page.has_text is True
        assert page.ocr_applied is True
        assert page.needs_ocr is False
        assert page.ocr_confidence == 0.92
        assert "INVOICE #999" in result.full_text
        assert mock_engine.call_count == 1

    def test_image_parser_corrupted_file(self, tmp_path):
        corrupt_path = tmp_path / "corrupt.jpg"
        corrupt_path.write_bytes(b"Not An Image Header At All")
        parser = ImageParser(ocr_engine=MockOCREngine())

        result = parser.parse(corrupt_path)
        assert result.status == ExtractionStatus.CORRUPTED
        assert "corrupted" in result.error_message.lower() or "unsupported" in result.error_message.lower()

    def test_image_parser_zero_byte_file(self, tmp_path):
        zero_path = tmp_path / "zero.png"
        zero_path.write_bytes(b"")
        parser = ImageParser(ocr_engine=MockOCREngine())

        result = parser.parse(zero_path)
        assert result.status == ExtractionStatus.EMPTY
        assert "empty" in result.error_message.lower()

    def test_image_parser_ocr_empty_output(self, tmp_path):
        img_path = create_synthetic_image(tmp_path / "blank_photo.png")
        # Simulate clean OCR that recognized 0 text tokens
        mock_engine = MockOCREngine(canned_text="", confidence=0.0)
        parser = ImageParser(ocr_engine=mock_engine)

        result = parser.parse(img_path)
        assert result.status == ExtractionStatus.EMPTY
        assert len(result.ocr_warnings) >= 1
        assert result.pages[0].ocr_applied is True
        assert result.pages[0].has_text is False

    def test_image_parser_ocr_engine_exception(self, tmp_path):
        img_path = create_synthetic_image(tmp_path / "crash.png")
        # Simulate OCR engine crash / out-of-memory
        mock_engine = MockOCREngine(simulate_exception=RuntimeError("CUDA/CPU Inference Crash"))
        parser = ImageParser(ocr_engine=mock_engine)

        result = parser.parse(img_path)
        assert result.status == ExtractionStatus.FAILED
        assert result.pages[0].ocr_applied is False
        assert result.pages[0].needs_ocr is True
        assert len(result.ocr_warnings) >= 1
        assert "CUDA/CPU Inference Crash" in result.ocr_warnings[0]

    def test_image_parser_unsupported_extension(self, tmp_path):
        """Enforces that ImageParser rejects unsupported file formats upfront."""
        bad_file = tmp_path / "document.pdf"
        bad_file.write_bytes(b"%PDF-1.4 header")
        parser = ImageParser(ocr_engine=MockOCREngine())

        result = parser.parse(bad_file)
        assert result.status == ExtractionStatus.FAILED
        assert "Unsupported image file extension" in result.error_message
        assert ".pdf" in result.error_message

    def test_image_parser_short_ocr_text_yields_empty(self, tmp_path):
        """
        Clarification test: OCR returning 1 or 2 words (< min_words_threshold=3)
        is classified as EMPTY to filter out noise, stray speckles, and watermark tokens.
        """
        img_path = create_synthetic_image(tmp_path / "noise.png")
        # 1 word only -> below substantive threshold (3)
        mock_engine = MockOCREngine(canned_text="WATERMARK", confidence=0.75)
        parser = ImageParser(ocr_engine=mock_engine, min_words_threshold=3)

        result = parser.parse(img_path)
        assert result.status == ExtractionStatus.EMPTY
        assert result.pages[0].has_text is False
        assert result.pages[0].ocr_applied is True
        assert result.pages[0].text == "WATERMARK"
        assert len(result.ocr_warnings) >= 1
        assert "below the substantive threshold" in result.ocr_warnings[0]


class TestPDFParserWithMockOCR:
    """Unit tests for PDFParser selective OCR integration using MockOCREngine."""

    def test_scanned_pdf_ocr_success(self, tmp_path):
        img_path = create_synthetic_image(tmp_path / "scan.png")
        pdf_path = create_scanned_pdf(tmp_path / "scanned.pdf", img_path)

        mock_engine = MockOCREngine(canned_text="EXTRACTED FROM SCANNED RECEIPT $95.00", confidence=0.88)
        parser = PDFParser(ocr_engine=mock_engine)

        result = parser.parse(pdf_path)
        assert result.status == ExtractionStatus.SUCCESS
        assert result.metadata.page_count == 1
        assert result.pages[0].ocr_applied is True
        assert result.pages[0].has_text is True
        assert result.pages[0].needs_ocr is False
        assert "RECEIPT $95.00" in result.full_text
        assert mock_engine.call_count == 1

    def test_scanned_pdf_ocr_empty_output(self, tmp_path):
        img_path = create_synthetic_image(tmp_path / "scan_empty.png")
        pdf_path = create_scanned_pdf(tmp_path / "scanned_empty.pdf", img_path)

        mock_engine = MockOCREngine(canned_text="", confidence=0.0)
        parser = PDFParser(ocr_engine=mock_engine)

        result = parser.parse(pdf_path)
        assert result.status == ExtractionStatus.EMPTY
        assert result.pages[0].ocr_applied is True
        assert result.pages[0].has_text is False
        assert len(result.ocr_warnings) >= 1

    def test_scanned_pdf_ocr_engine_crash_returns_failed(self, tmp_path):
        img_path = create_synthetic_image(tmp_path / "scan_crash.png")
        pdf_path = create_scanned_pdf(tmp_path / "scanned_crash.pdf", img_path)

        mock_engine = MockOCREngine(simulate_exception=RuntimeError("Memory Allocation Failure"))
        parser = PDFParser(ocr_engine=mock_engine)

        result = parser.parse(pdf_path)
        # All pages crashed -> FAILED (not silently marked as EMPTY)
        assert result.status == ExtractionStatus.FAILED
        assert result.pages[0].ocr_applied is False
        assert result.pages[0].needs_ocr is True
        assert len(result.ocr_warnings) >= 1
        assert "Memory Allocation Failure" in result.ocr_warnings[0]

    def test_mixed_pdf_ocr_success(self, tmp_path):
        img_path = create_synthetic_image(tmp_path / "p2_img.png")
        pdf_path = create_mixed_digital_scanned_pdf(tmp_path / "mixed.pdf", img_path)

        mock_engine = MockOCREngine(canned_text="Page 2 Scanned Receipt Itemized $300.00", confidence=0.90)
        parser = PDFParser(ocr_engine=mock_engine)

        result = parser.parse(pdf_path)
        assert result.status == ExtractionStatus.SUCCESS
        assert result.metadata.page_count == 2
        # Page 1: Digital text (OCR was NOT applied)
        assert result.pages[0].has_text is True
        assert result.pages[0].ocr_applied is False
        assert "Purchase Agreement Digital Header" in result.pages[0].text
        # Page 2: Scanned image (OCR was applied)
        assert result.pages[1].has_text is True
        assert result.pages[1].ocr_applied is True
        assert "Page 2 Scanned Receipt" in result.pages[1].text
        # Consolidated text contains both
        assert "Purchase Agreement Digital Header" in result.full_text
        assert "Page 2 Scanned Receipt" in result.full_text
        # Mock engine was called exactly once (Page 2 only)
        assert mock_engine.call_count == 1

    def test_mixed_pdf_ocr_crash_preserves_digital_text(self, tmp_path):
        img_path = create_synthetic_image(tmp_path / "p2_crash.png")
        pdf_path = create_mixed_digital_scanned_pdf(tmp_path / "mixed_crash.pdf", img_path)

        # Page 2 OCR will crash
        mock_engine = MockOCREngine(simulate_exception=ValueError("Unsupported color palette"))
        parser = PDFParser(ocr_engine=mock_engine)

        result = parser.parse(pdf_path)
        # Page 1 digital text preserved -> PARTIAL_SUCCESS (not FAILED or EMPTY)
        assert result.status == ExtractionStatus.PARTIAL_SUCCESS
        assert "Purchase Agreement Digital Header" in result.full_text
        assert result.pages[0].has_text is True
        assert result.pages[1].ocr_applied is False
        assert result.pages[1].needs_ocr is True
        assert len(result.ocr_warnings) >= 1
        assert "Unsupported color palette" in result.ocr_warnings[0]

    def test_mixed_pdf_ocr_empty_output_returns_partial_success(self, tmp_path):
        """Mixed digital + scanned where OCR completes cleanly on Page 2 but recognizes 0 text."""
        img_path = create_synthetic_image(tmp_path / "p2_empty_scan.png")
        pdf_path = create_mixed_digital_scanned_pdf(tmp_path / "mixed_empty_scan.pdf", img_path)

        # Page 2 OCR returns empty text cleanly
        mock_engine = MockOCREngine(canned_text="", confidence=0.0)
        parser = PDFParser(ocr_engine=mock_engine)

        result = parser.parse(pdf_path)
        # Page 1 digital text is preserved, Page 2 OCR completed but empty -> PARTIAL_SUCCESS
        assert result.status == ExtractionStatus.PARTIAL_SUCCESS
        assert "Purchase Agreement Digital Header" in result.full_text
        assert result.pages[0].has_text is True
        assert result.pages[0].ocr_applied is False
        assert result.pages[1].ocr_applied is True
        assert result.pages[1].has_text is False
        assert len(result.ocr_warnings) >= 1
        assert "no adequate text was recognized" in result.ocr_warnings[0]

    def test_blank_page_never_triggers_ocr(self, tmp_path):
        img_path = create_synthetic_image(tmp_path / "p2_img2.png")
        pdf_path = create_mixed_three_page_with_blank(tmp_path / "three_page_blank.pdf", img_path)

        mock_engine = MockOCREngine(canned_text="Page 2 Scanned Content 12345", confidence=0.85)
        parser = PDFParser(ocr_engine=mock_engine)

        result = parser.parse(pdf_path)
        assert result.status == ExtractionStatus.SUCCESS
        assert result.metadata.page_count == 3
        # Page 1: Digital text
        assert result.pages[0].has_text is True
        # Page 2: Scanned OCR
        assert result.pages[1].ocr_applied is True
        # Page 3: Blank page must NEVER have OCR applied
        assert result.pages[2].is_blank is True
        assert result.pages[2].ocr_applied is False
        assert result.pages[2].needs_ocr is False
        # Engine called only once (for Page 2)
        assert mock_engine.call_count == 1

    def test_zero_text_ocr_exception_plus_ocr_empty_returns_failed(self, tmp_path):
        """
        Two-page scanned PDF with zero digital text:
        - Page 1: OCR engine exception
        - Page 2: OCR completes but returns empty text
        Expected outcome: FAILED (because fatal OCR exception occurred and 0 text was extracted anywhere).
        """
        img_path = create_synthetic_image(tmp_path / "scan_sub.png")
        pdf_path = create_two_page_scanned_pdf(tmp_path / "two_scanned.pdf", img_path)

        mock_engine = MockOCREngine(
            responses=[
                RuntimeError("Page 1 GPU/CPU Allocation Crash"),
                OCRResult(text="", confidence=0.0),
            ]
        )
        parser = PDFParser(ocr_engine=mock_engine)

        result = parser.parse(pdf_path)
        assert result.status == ExtractionStatus.FAILED
        assert result.metadata.page_count == 2
        # Page 1 failed OCR
        assert result.pages[0].ocr_applied is False
        assert result.pages[0].needs_ocr is True
        # Page 2 ran OCR but recognized no text
        assert result.pages[1].ocr_applied is True
        assert result.pages[1].has_text is False
        assert result.pages[1].needs_ocr is False
        # Both diagnostics recorded in ocr_warnings
        assert len(result.ocr_warnings) == 2
        assert "Page 1 GPU/CPU Allocation Crash" in result.ocr_warnings[0]
        assert "no adequate text was recognized" in result.ocr_warnings[1]

    def test_sparse_digital_page_handling_with_ocr(self, tmp_path):
        """
        Tests sparse digital page handling (pages with < 5 words and zero images):
        Case A: Substantive digital page + sparse digital page -> PARTIAL_SUCCESS.
        Case B: Sparse digital page only -> EMPTY (substantive word count below threshold).
        """
        # Case A: Digital text + sparse digital page
        pdf_a = create_digital_plus_sparse_pdf(tmp_path / "text_plus_sparse.pdf")
        parser = PDFParser(ocr_engine=MockOCREngine())
        res_a = parser.parse(pdf_a)
        assert res_a.status == ExtractionStatus.PARTIAL_SUCCESS
        assert res_a.pages[0].has_text is True
        assert res_a.pages[1].has_text is False
        assert res_a.pages[1].is_blank is False
        assert res_a.pages[1].needs_ocr is False

        # Case B: Sparse digital page only
        pdf_b = create_sparse_text_pdf(tmp_path / "sparse_only.pdf", text="Confidential")
        res_b = parser.parse(pdf_b)
        assert res_b.status == ExtractionStatus.EMPTY
        assert res_b.pages[0].has_text is False
        assert res_b.pages[0].is_blank is False
        assert res_b.pages[0].needs_ocr is False


class TestDigitalOnlyModeBranches:
    """Explicit tests for all digital-only (enable_ocr=False) status branches."""

    def test_digital_only_mixed_digital_and_scanned(self, tmp_path):
        """Mixed digital + scanned with enable_ocr=False yields PARTIAL_SUCCESS and flags needs_ocr=True."""
        img_path = create_synthetic_image(tmp_path / "p2_img.png")
        pdf_path = create_mixed_digital_scanned_pdf(tmp_path / "mixed_dig.pdf", img_path)
        parser = PDFParser(enable_ocr=False)

        result = parser.parse(pdf_path)
        assert result.status == ExtractionStatus.PARTIAL_SUCCESS
        assert result.pages[0].has_text is True
        assert result.pages[1].needs_ocr is True
        assert result.pages[1].ocr_applied is False

    def test_digital_only_scanned_only(self, tmp_path):
        """Scanned image only with enable_ocr=False yields NEEDS_OCR."""
        img_path = create_synthetic_image(tmp_path / "scan_dig.png")
        pdf_path = create_scanned_pdf(tmp_path / "scanned_dig.pdf", img_path)
        parser = PDFParser(enable_ocr=False)

        result = parser.parse(pdf_path)
        assert result.status == ExtractionStatus.NEEDS_OCR
        assert result.pages[0].needs_ocr is True
        assert result.pages[0].ocr_applied is False

    def test_digital_only_digital_plus_sparse(self, tmp_path):
        """Digital page + sparse page with enable_ocr=False yields PARTIAL_SUCCESS."""
        pdf_path = create_digital_plus_sparse_pdf(tmp_path / "dig_sparse.pdf")
        parser = PDFParser(enable_ocr=False)

        result = parser.parse(pdf_path)
        assert result.status == ExtractionStatus.PARTIAL_SUCCESS
        assert result.pages[0].has_text is True
        assert result.pages[1].has_text is False
        assert result.pages[1].needs_ocr is False

    def test_digital_only_sparse_only(self, tmp_path):
        """Sparse text only with enable_ocr=False yields PARTIAL_SUCCESS."""
        pdf_path = create_sparse_text_pdf(tmp_path / "sparse_only_dig.pdf")
        parser = PDFParser(enable_ocr=False)

        result = parser.parse(pdf_path)
        assert result.status == ExtractionStatus.PARTIAL_SUCCESS
        assert result.pages[0].has_text is False
        assert result.pages[0].needs_ocr is False


# --- Real EasyOCR Smoke Test (Strictly Opt-In) ---

@pytest.mark.skipif(
    os.environ.get("RUN_REAL_OCR_SMOKE") != "1",
    reason="Real EasyOCR smoke test is opt-in; set RUN_REAL_OCR_SMOKE=1 to run"
)
def test_easyocr_real_smoke(tmp_path):
    """
    Opt-in smoke test for real EasyOCR engine.
    - If model download fails due to verified network error, test skips with documented reason.
    - If model loads, inference crash or missing expected text FAILS the test.
    """
    try:
        engine = EasyOCREngine()
        # Trigger lazy model load
        _ = engine.reader
    except (urllib.error.URLError, socket.gaierror, TimeoutError, ConnectionError, OSError) as net_err:
        pytest.skip(f"EasyOCR model weights download unavailable due to network: {net_err}")

    # Create synthetic test image
    img_path = create_synthetic_image(tmp_path / "real_smoke.png", text="INVOICE #9988 TOTAL $500.00")
    
    # Inference execution (unexpected exceptions will fail the test naturally)
    result = engine.extract_text(img_path)

    # Correctness assertions: expected text must be found
    assert "INVOICE" in result.text or "9988" in result.text or "500" in result.text, (
        f"Real OCR inference completed but did not find expected text. Output: '{result.text}'"
    )
    assert 0.0 <= result.confidence <= 1.0, f"Confidence out of range: {result.confidence}"
    assert result.engine_name == "easyocr"
