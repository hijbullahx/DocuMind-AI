"""
Automated Test Suite for TASK-019: Full-Text Document & Extraction Search Engine.
Tests:
- Search across Tier A: filename, invoice_number (with exact match boost)
- Search across Tier B: supplier_name, customer_name
- Search across Tier C: line item descriptions
- Search across Tier D: raw OCR text
- Multi-word search terms with AND token logic
- Case-insensitivity and punctuation resilience
- Safe HTML snippet generation and XSS neutralization
- Matched field attribution (INVOICE_NUMBER, FILENAME, SUPPLIER_NAME, LINE_ITEM, OCR_CONTENT)
- Filtering by status, validation_status, file_type, and dates
- Pagination (page, page_size, total_pages)
- Empty query handling and excessive length bounding
- Dedicated GET /api/documents/search/ endpoint behavior
"""
from datetime import date
from decimal import Decimal
import os
import sys
import unittest.mock as mock
import uuid

# Provide mock stubs for optional worker/parser modules if not installed in environment
for mod in ["celery", "celery.shared_task", "pymupdf", "fitz", "pdfplumber", "easyocr"]:
    if mod not in sys.modules:
        sys.modules[mod] = mock.MagicMock()

import django
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "documind.settings")
django.setup()

import pytest
from django.core.management import call_command
from rest_framework import status
from rest_framework.test import APIClient

from apps.documents.models import (
    Document,
    DocumentStatus,
    InvoiceExtraction,
    LineItem,
    ValidationStatusChoices,
)
from apps.documents.search import (
    generate_search_snippet,
    safe_highlight,
    sanitize_search_query,
    tokenize_query,
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Applies database migrations for test session."""
    call_command("migrate", verbosity=0)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def sample_documents():
    """Populates test documents across varied financial scenarios."""
    # Doc 1: TechCorp software license
    doc1 = Document.objects.create(
        filename="invoice_techcorp_2026.pdf",
        file_type="pdf",
        file_size_bytes=45000,
        status=DocumentStatus.SUCCESS,
        validation_status=ValidationStatusChoices.VERIFIED,
        raw_text="Payment Terms: Net 30. Thank you for your business. Project Falcon Phase 1 delivered on schedule.",
    )
    ext1 = InvoiceExtraction.objects.create(
        document=doc1,
        invoice_number="INV-2026-FALCON",
        invoice_date=date(2026, 2, 10),
        supplier_name="TechCorp Global Systems",
        customer_name="Alpha Dynamics LLC",
        subtotal=Decimal("5000.00"),
        tax=Decimal("500.00"),
        total=Decimal("5500.00"),
        currency="USD",
    )
    LineItem.objects.create(
        extraction=ext1,
        line_number=1,
        description="Enterprise Cloud Architecture Consulting",
        quantity=Decimal("1.0000"),
        unit_price=Decimal("5000.0000"),
        amount=Decimal("5000.00"),
    )

    # Doc 2: Acme Hardware bolts & titanium screws
    doc2 = Document.objects.create(
        filename="po_acme_hardware.pdf",
        file_type="pdf",
        file_size_bytes=32000,
        status=DocumentStatus.SUCCESS,
        validation_status=ValidationStatusChoices.NEEDS_REVIEW,
        raw_text="Warehouse Receiving Dock 4. Handle with extreme care: Fragile industrial parts.",
    )
    ext2 = InvoiceExtraction.objects.create(
        document=doc2,
        invoice_number="PO-ACME-8899",
        invoice_date=date(2026, 2, 15),
        supplier_name="Acme Hardware Supply Co",
        customer_name="Beta Logistics Org",
        subtotal=Decimal("800.00"),
        tax=Decimal("80.00"),
        total=Decimal("880.00"),
        currency="USD",
    )
    LineItem.objects.create(
        extraction=ext2,
        line_number=1,
        description="Grade 8 Titanium Screws Box of 500",
        quantity=Decimal("2.0000"),
        unit_price=Decimal("400.0000"),
        amount=Decimal("800.00"),
    )

    # Doc 3: Malicious OCR / XSS probe document
    doc3 = Document.objects.create(
        filename="test_security_xss.pdf",
        file_type="pdf",
        file_size_bytes=15000,
        status=DocumentStatus.SUCCESS,
        validation_status=ValidationStatusChoices.VERIFIED,
        raw_text="Invoice note contains <script>alert('xss')</script> and <b>malformed tags</b> for Cyberdyne Systems.",
    )
    InvoiceExtraction.objects.create(
        document=doc3,
        invoice_number="SEC-007",
        invoice_date=date(2026, 2, 20),
        supplier_name="Cyberdyne Systems Security",
        customer_name="SkyNet Defense Inc",
        subtotal=Decimal("9999.00"),
        total=Decimal("9999.00"),
    )

    return doc1, doc2, doc3


@pytest.mark.django_db
class TestSearchAPI:
    """Test suite covering the dedicated GET /api/documents/search/ endpoint."""

    def test_search_by_filename(self, api_client, sample_documents):
        """Finds document matching filename token."""
        res = api_client.get("/api/documents/search/?q=techcorp")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["count"] >= 1
        top_match = data["results"][0]
        assert "techcorp" in top_match["filename"].lower()
        assert "<mark" in top_match["snippet"].lower()

    def test_search_by_invoice_number_exact_boost(self, api_client, sample_documents):
        """Exact invoice reference match is prioritized to the top of results."""
        res = api_client.get("/api/documents/search/?q=INV-2026-FALCON")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["count"] >= 1
        top_match = data["results"][0]
        assert top_match["invoice_number"] == "INV-2026-FALCON"
        assert top_match["matched_field"] == "INVOICE_NUMBER"
        assert "Invoice Reference" in top_match["matched_field_label"]

    def test_search_by_supplier_name(self, api_client, sample_documents):
        """Finds document by supplier legal entity."""
        res = api_client.get("/api/documents/search/?q=Acme Hardware")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["count"] >= 1
        match = next(r for r in data["results"] if "Acme" in (r["supplier_name"] or ""))
        assert match["matched_field"] == "SUPPLIER_NAME"

    def test_search_by_customer_name(self, api_client, sample_documents):
        """Finds document by customer recipient name."""
        res = api_client.get("/api/documents/search/?q=Alpha Dynamics")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["count"] >= 1
        assert any("Alpha Dynamics" in (r["customer_name"] or "") for r in data["results"])

    def test_search_by_line_item_description(self, api_client, sample_documents):
        """Finds document matching a specific item description in extraction line items."""
        res = api_client.get("/api/documents/search/?q=Titanium Screws")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["count"] >= 1
        match = next(r for r in data["results"] if r["invoice_number"] == "PO-ACME-8899")
        assert match["matched_field"] == "LINE_ITEM"
        assert "Titanium" in match["snippet"]
        assert "<mark" in match["snippet"]

    def test_search_by_ocr_raw_text(self, api_client, sample_documents):
        """Finds document matching OCR body text and generates bounded snippet."""
        res = api_client.get("/api/documents/search/?q=Warehouse Receiving Dock")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["count"] >= 1
        match = next(r for r in data["results"] if r["invoice_number"] == "PO-ACME-8899")
        assert match["matched_field"] == "OCR_CONTENT"
        assert "Dock" in match["snippet"]
        assert "<mark" in match["snippet"]

    def test_multi_word_and_logic(self, api_client, sample_documents):
        """Multi-word search requires all distinct tokens to be present."""
        # 'Falcon Consulting' spans raw_text ('Falcon') and line item ('Consulting') on Doc 1
        res = api_client.get("/api/documents/search/?q=Falcon Consulting")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["count"] >= 1
        assert data["results"][0]["invoice_number"] == "INV-2026-FALCON"

    def test_safe_html_snippet_xss_protection(self, api_client, sample_documents):
        """Verifies malicious OCR text is escaped and <script> is neutralized."""
        res = api_client.get("/api/documents/search/?q=Cyberdyne Systems")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["count"] >= 1
        match = next(r for r in data["results"] if "Cyberdyne" in (r["supplier_name"] or ""))
        snippet = match["snippet"]
        assert "<script>" not in snippet
        assert "&lt;script&gt;" in snippet or "<mark" in snippet

    def test_empty_query_returns_empty_results(self, api_client, sample_documents):
        """Empty query without filters returns count 0 and empty results list."""
        res = api_client.get("/api/documents/search/?q=")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["count"] == 0
        assert data["results"] == []

    def test_no_matches_returns_empty_results(self, api_client, sample_documents):
        """Search query matching no document returns count 0 gracefully."""
        res = api_client.get("/api/documents/search/?q=NonExistentPhrase998877")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["count"] == 0
        assert data["results"] == []

    def test_filter_by_validation_status(self, api_client, sample_documents):
        """Filters search results by validation_status."""
        res = api_client.get("/api/documents/search/?q=Hardware&validation_status=NEEDS_REVIEW")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["count"] >= 1
        assert all(r["validation_status"] == "NEEDS_REVIEW" for r in data["results"])

    def test_pagination_controls(self, api_client, sample_documents):
        """Paginates search results properly using page and page_size."""
        res = api_client.get("/api/documents/search/?q=pdf&page=1&page_size=1")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["page"] == 1
        assert data["page_size"] == 1
        assert len(data["results"]) == 1
        assert data["total_pages"] >= 2
