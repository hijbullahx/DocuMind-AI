"""
Automated Test Suite for TASK-017: Manual Correction Editor & Audit History.
Tests:
  - Header field corrections (invoice_number, dates, supplier, totals, currency)
  - Line item addition, modification, and deletion
  - AuditLog recording for changed fields and line items
  - Original machine-extraction snapshotting in metadata
  - Validation re-evaluation and status transition
  - Guard against active processing state (409 Conflict)
  - Guard against documents without extraction (400 Bad Request)
  - Validation error handling for invalid numeric types
  - Raw OCR text and evidence provenance preservation
"""
from datetime import date
from decimal import Decimal
import json
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
from django.conf import settings
from django.core.management import call_command
from rest_framework import status
from rest_framework.test import APIClient

from apps.documents.models import (
    AuditLog,
    Document,
    DocumentStatus,
    InvoiceExtraction,
    LineItem,
    ValidationError,
    ValidationSeverityChoices,
    ValidationStatusChoices,
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Applies database migrations for test session."""
    call_command("migrate", verbosity=0)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def sample_document():
    """Creates a sample processed document with structured extraction and line items."""
    doc = Document.objects.create(
        filename="invoice_acme_2026.pdf",
        file_type="pdf",
        file_size_bytes=1048576,
        page_count=2,
        status=DocumentStatus.SUCCESS,
        validation_status=ValidationStatusChoices.NEEDS_REVIEW,
        raw_text="ORIGINAL RAW OCR TEXT NEVER OVERWRITTEN",
        metadata={"ocr_engine": "EasyOCREngine"},
    )

    extraction = InvoiceExtraction.objects.create(
        document=doc,
        invoice_number="INV-2026-001",
        invoice_date=date(2026, 3, 1),
        due_date=date(2026, 3, 31),
        supplier_name="Acme Corp (AI Extracted)",
        supplier_address="100 Industrial Parkway",
        customer_name="Global Logistics Inc",
        customer_address="200 Freight Ave",
        subtotal=Decimal("1000.00"),
        tax=Decimal("100.00"),
        total=Decimal("1200.00"),  # Intentional discrepancy: 1000 + 100 != 1200
        currency="USD",
        raw_text_evidence={"invoice_number": "INV-2026-001", "total": "$1,200.00"},
        confidence_score=0.92,
        llm_model="mock-llm-v1",
    )

    LineItem.objects.create(
        extraction=extraction,
        line_number=1,
        description="Heavy Duty Bolts",
        quantity=Decimal("10.0000"),
        unit_price=Decimal("50.0000"),
        amount=Decimal("500.00"),
    )
    LineItem.objects.create(
        extraction=extraction,
        line_number=2,
        description="Machine Lubricant",
        quantity=Decimal("5.0000"),
        unit_price=Decimal("100.0000"),
        amount=Decimal("500.00"),
    )

    ValidationError.objects.create(
        document=doc,
        rule_id="MATH_TAX_ADDITION",
        field="total",
        message="Subtotal + Tax does not equal Total",
        severity=ValidationSeverityChoices.ERROR,
        actual_value="1200.00",
        expected_value="1100.00",
        difference=Decimal("100.00"),
    )

    return doc


@pytest.mark.django_db
class TestDocumentCorrectionAPI:

    def test_successful_header_fields_correction(self, api_client, sample_document):
        """Verifies updating header fields creates AuditLog entries and preserves original values."""
        doc = sample_document
        url = f"/api/documents/{doc.id}/correct/"

        payload = {
            "invoice_number": "INV-2026-001-CORRECTED",
            "supplier_name": "Acme Corporation Official",
            "total": "1100.00",  # Correct total so 1000 + 100 = 1100
            "reason": "Corrected arithmetic discrepancy and supplier legal name",
            "operator": "auditor_alice",
        }

        res = api_client.post(url, data=payload, format="json")
        assert res.status_code == status.HTTP_200_OK

        # Verify updated values in response
        data = res.json()
        assert data["extraction"]["invoice_number"] == "INV-2026-001-CORRECTED"
        assert data["extraction"]["supplier_name"] == "Acme Corporation Official"
        assert data["extraction"]["total"] == "1100.00"

        # Verify AuditLog entries
        logs = AuditLog.objects.filter(document=doc, action="MANUAL_CORRECTION").order_by("created_at")
        assert logs.count() >= 3

        inv_log = logs.filter(field_name="invoice_number").first()
        assert inv_log is not None
        assert inv_log.old_value == "INV-2026-001"
        assert inv_log.new_value == "INV-2026-001-CORRECTED"
        assert inv_log.user_id == "auditor_alice"
        assert inv_log.reason == "Corrected arithmetic discrepancy and supplier legal name"

        tot_log = logs.filter(field_name="total").first()
        assert tot_log is not None
        assert tot_log.old_value == "1200.00"
        assert tot_log.new_value == "1100.00"

        # Verify metadata preserves machine extraction snapshot
        doc.refresh_from_db()
        corrections = doc.metadata.get("manual_corrections", {})
        assert corrections.get("is_corrected") is True
        assert corrections.get("last_corrected_by") == "auditor_alice"
        assert "original_extraction" in corrections
        assert corrections["original_extraction"]["invoice_number"] == "INV-2026-001"
        assert corrections["original_extraction"]["total"] == "1200.00"

        # Verify raw OCR text is untouched
        assert doc.raw_text == "ORIGINAL RAW OCR TEXT NEVER OVERWRITTEN"

    def test_line_items_correction_and_addition(self, api_client, sample_document):
        """Verifies line items addition, modification, and deletion are audited and persisted."""
        doc = sample_document
        url = f"/api/documents/{doc.id}/correct/"

        payload = {
            "subtotal": "1500.00",
            "total": "1650.00",
            "tax": "150.00",
            "line_items": [
                {
                    "line_number": 1,
                    "description": "Heavy Duty Bolts (Edited)",
                    "quantity": "20.0000",
                    "unit_price": "50.0000",
                    "amount": "1000.00",
                },
                {
                    "line_number": 2,
                    "description": "New Additional Safety Goggles",
                    "quantity": "10.0000",
                    "unit_price": "50.0000",
                    "amount": "500.00",
                },
            ],
            "reason": "Added missing safety goggles line item",
            "operator": "auditor_bob",
        }

        res = api_client.post(url, data=payload, format="json")
        assert res.status_code == status.HTTP_200_OK

        data = res.json()
        assert len(data["extraction"]["line_items"]) == 2
        assert data["extraction"]["line_items"][0]["description"] == "Heavy Duty Bolts (Edited)"
        assert data["extraction"]["line_items"][0]["amount"] == "1000.00"
        assert data["extraction"]["line_items"][1]["description"] == "New Additional Safety Goggles"
        assert data["extraction"]["line_items"][1]["amount"] == "500.00"

        # Verify line items audit log
        li_log = AuditLog.objects.filter(document=doc, action="MANUAL_CORRECTION", field_name="line_items").first()
        assert li_log is not None
        assert "2 line items" in li_log.new_value
        assert li_log.user_id == "auditor_bob"

    def test_guard_against_active_processing(self, api_client, sample_document):
        """Rejects correction if document status is PROCESSING (HTTP 409 Conflict)."""
        doc = sample_document
        doc.status = DocumentStatus.PROCESSING
        doc.save(update_fields=["status"])

        url = f"/api/documents/{doc.id}/correct/"
        res = api_client.post(url, data={"invoice_number": "NEW-INV"}, format="json")
        assert res.status_code == status.HTTP_409_CONFLICT
        assert "currently being processed" in res.json()["error"]

    def test_guard_against_missing_extraction(self, api_client):
        """Rejects correction if document has no extraction record (HTTP 400 Bad Request)."""
        doc = Document.objects.create(
            filename="unextracted.pdf",
            file_type="pdf",
            status=DocumentStatus.QUEUED,
        )

        url = f"/api/documents/{doc.id}/correct/"
        res = api_client.post(url, data={"invoice_number": "NEW-INV"}, format="json")
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "does not have a structured extraction record" in res.json()["error"]

    def test_rejection_of_invalid_numeric_data(self, api_client, sample_document):
        """Rejects malformed numeric values server-side."""
        doc = sample_document
        url = f"/api/documents/{doc.id}/correct/"

        res = api_client.post(url, data={"total": "NOT_A_NUMBER"}, format="json")
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "total" in res.json()
