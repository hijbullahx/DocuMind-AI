"""
Comprehensive Test Suite for TASK-012: Document REST API Layer.
Tests Document Upload, Listing, Filtering, Detail Inspection, Status Polling,
Reprocessing/Retry, Cross-Document Reconciliation, Security Constraints, and Error Handling.
"""
from datetime import date
from decimal import Decimal
import io
import json
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch
import uuid

import django
import pytest

# Initialize Django environment
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "documind.settings")
django.setup()

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from rest_framework import status
from rest_framework.test import APIClient

from apps.documents.models import (
    AuditLog,
    CrossReconciliation,
    Document,
    DocumentStatus,
    InvoiceExtraction,
    LineItem,
    ValidationError,
    ValidationSeverityChoices,
    ValidationStatusChoices,
)


@pytest.fixture(scope="session", autouse=True)
def setup_api_test_env():
    """Applies migrations once for test session and enables Celery eager mode."""
    call_command("migrate", verbosity=0)
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


class BaseAPITest:
    """Base class providing per-test database isolation for API test cases."""

    @pytest.fixture(autouse=True)
    def clean_api_db(self):
        CrossReconciliation.objects.all().delete()
        AuditLog.objects.all().delete()
        ValidationError.objects.all().delete()
        LineItem.objects.all().delete()
        InvoiceExtraction.objects.all().delete()
        Document.objects.all().delete()
        yield
        CrossReconciliation.objects.all().delete()
        AuditLog.objects.all().delete()
        ValidationError.objects.all().delete()
        LineItem.objects.all().delete()
        InvoiceExtraction.objects.all().delete()
        Document.objects.all().delete()


@pytest.fixture
def client():
    """Returns a fresh DRF APIClient."""
    return APIClient()


# =========================================================================
# 1. Document Upload API Tests (POST /api/documents/)
# =========================================================================

class TestDocumentUploadAPI(BaseAPITest):
    """Verifies file validation, upload constraints, and Celery task dispatch."""

    def test_upload_valid_file_enqueues_task(self, client):
        """Tests uploading a valid PDF document creates record and dispatches Celery task."""
        file_content = b"%PDF-1.4 Mock PDF content"
        uploaded = SimpleUploadedFile("invoice_2024.pdf", file_content, content_type="application/pdf")

        with patch("apps.documents.views.process_document_task.delay") as mock_task:
            response = client.post("/api/documents/", {"file": uploaded}, format="multipart")

        assert response.status_code == status.HTTP_201_CREATED
        data = response.data
        assert "id" in data
        assert data["filename"] == "invoice_2024.pdf"
        assert data["file_type"] == "pdf"
        assert data["file_size_bytes"] == len(file_content)
        assert data["status"] == DocumentStatus.QUEUED
        assert data["validation_status"] == ValidationStatusChoices.PENDING

        # Verify Celery task dispatched with document ID
        mock_task.assert_called_once_with(str(data["id"]))

        # Verify DB record
        doc = Document.objects.get(id=data["id"])
        assert doc.filename == "invoice_2024.pdf"
        assert doc.status == DocumentStatus.QUEUED

    def test_upload_valid_raw_text(self, client):
        """Tests uploading direct raw text without a physical file."""
        text_content = "Invoice INV-001\nTotal: $100.00"

        with patch("apps.documents.views.process_document_task.delay") as mock_task:
            response = client.post("/api/documents/", {"raw_text": text_content}, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        data = response.data
        assert data["file_type"] == "txt"
        assert data["status"] == DocumentStatus.QUEUED
        mock_task.assert_called_once_with(str(data["id"]))

    def test_upload_empty_request_rejected(self, client):
        """Tests that submitting empty request without file or raw_text returns 400."""
        response = client.post("/api/documents/", {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "file" in response.data

    def test_upload_empty_file_rejected(self, client):
        """Tests that an empty (0 bytes) file is rejected with 400 Bad Request."""
        empty_file = SimpleUploadedFile("empty.pdf", b"", content_type="application/pdf")
        response = client.post("/api/documents/", {"file": empty_file}, format="multipart")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "empty" in str(response.data["file"][0]).lower()

    def test_upload_unsupported_file_extension_rejected(self, client):
        """Tests that unsupported file extensions (e.g. .exe, .sh) are rejected with 400."""
        bad_file = SimpleUploadedFile("malicious.exe", b"MZBinaryPayload", content_type="application/octet-stream")
        response = client.post("/api/documents/", {"file": bad_file}, format="multipart")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "unsupported file extension" in str(response.data["file"][0]).lower()

    def test_upload_file_size_limit_exceeded(self, client):
        """Tests that files exceeding MAX_UPLOAD_SIZE_BYTES are rejected with 400."""
        # Temporarily mock MAX_UPLOAD_SIZE_BYTES to 100 bytes
        with patch.object(settings, "MAX_UPLOAD_SIZE_BYTES", 100):
            big_file = SimpleUploadedFile("oversized.pdf", b"X" * 200, content_type="application/pdf")
            response = client.post("/api/documents/", {"file": big_file}, format="multipart")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "exceeds maximum allowed limit" in str(response.data["file"][0]).lower()

    def test_client_cannot_tamper_internal_status_fields(self, client):
        """Tests security: client-supplied status or error_message in upload request is ignored."""
        uploaded = SimpleUploadedFile("invoice.pdf", b"%PDF content", content_type="application/pdf")
        payload = {
            "file": uploaded,
            "status": "SUCCESS",  # Attempt to spoof status
            "validation_status": "VERIFIED",
            "error_message": "Fake error",
        }

        with patch("apps.documents.views.process_document_task.delay"):
            response = client.post("/api/documents/", payload, format="multipart")

        assert response.status_code == status.HTTP_201_CREATED
        doc = Document.objects.get(id=response.data["id"])
        # Status MUST remain QUEUED regardless of client input
        assert doc.status == DocumentStatus.QUEUED
        assert doc.validation_status == ValidationStatusChoices.PENDING
        assert doc.error_message is None


# =========================================================================
# 2. Document List & Pagination API Tests (GET /api/documents/)
# =========================================================================

class TestDocumentListAPI(BaseAPITest):
    """Verifies listing, pagination, filtering by status, search, and ordering."""

    def test_list_documents_pagination(self, client):
        """Tests paginated retrieval of documents."""
        for i in range(25):
            Document.objects.create(
                filename=f"doc_{i:02d}.pdf",
                file_type="pdf",
                status=DocumentStatus.SUCCESS,
            )

        response = client.get("/api/documents/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert data["count"] == 25
        assert len(data["results"]) == 20  # Default page size = 20
        assert data["next"] is not None

        # Fetch page 2
        page2_res = client.get(data["next"])
        assert page2_res.status_code == status.HTTP_200_OK
        assert len(page2_res.data["results"]) == 5

    def test_filter_by_status(self, client):
        """Tests filtering document list by ?status= query parameter."""
        Document.objects.create(filename="queued.pdf", file_type="pdf", status=DocumentStatus.QUEUED)
        Document.objects.create(filename="processing.pdf", file_type="pdf", status=DocumentStatus.PROCESSING)
        Document.objects.create(filename="success.pdf", file_type="pdf", status=DocumentStatus.SUCCESS)

        # Filter by QUEUED
        res = client.get("/api/documents/?status=QUEUED")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 1
        assert res.data["results"][0]["filename"] == "queued.pdf"

        # Filter by SUCCESS
        res_success = client.get("/api/documents/?status=SUCCESS")
        assert res_success.data["count"] == 1
        assert res_success.data["results"][0]["filename"] == "success.pdf"

    def test_filter_by_validation_status(self, client):
        """Tests filtering document list by ?validation_status= query parameter."""
        Document.objects.create(
            filename="verified.pdf", file_type="pdf",
            validation_status=ValidationStatusChoices.VERIFIED,
        )
        Document.objects.create(
            filename="failed.pdf", file_type="pdf",
            validation_status=ValidationStatusChoices.FAILED,
        )

        res = client.get("/api/documents/?validation_status=VERIFIED")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 1
        assert res.data["results"][0]["filename"] == "verified.pdf"

    def test_search_documents(self, client):
        """Tests search by filename, invoice number, or supplier name."""
        doc1 = Document.objects.create(filename="alpha_corp_invoice.pdf", file_type="pdf")
        InvoiceExtraction.objects.create(
            document=doc1,
            invoice_number="INV-ALPHA-100",
            supplier_name="Alpha Corporation",
            total=Decimal("500.00"),
        )

        doc2 = Document.objects.create(filename="beta_services.xlsx", file_type="xlsx")
        InvoiceExtraction.objects.create(
            document=doc2,
            invoice_number="INV-BETA-200",
            supplier_name="Beta Logistics",
            total=Decimal("750.00"),
        )

        # Search by supplier name
        res = client.get("/api/documents/?search=Alpha")
        assert res.data["count"] == 1
        assert res.data["results"][0]["id"] == str(doc1.id)

        # Search by invoice number
        res_inv = client.get("/api/documents/?search=BETA-200")
        assert res_inv.data["count"] == 1
        assert res_inv.data["results"][0]["id"] == str(doc2.id)

        # Search by filename
        res_file = client.get("/api/documents/?search=services.xlsx")
        assert res_file.data["count"] == 1
        assert res_file.data["results"][0]["id"] == str(doc2.id)


# =========================================================================
# 3. Document Detail API Tests (GET /api/documents/{id}/)
# =========================================================================

class TestDocumentDetailAPI(BaseAPITest):
    """Verifies detailed document inspection including nested extractions, line items, and errors."""

    def test_get_document_detail_success(self, client):
        """Tests retrieving full document details with nested extraction and validation errors."""
        doc = Document.objects.create(
            filename="detailed_inv.pdf",
            file_type="pdf",
            file_size_bytes=1024,
            page_count=2,
            status=DocumentStatus.SUCCESS,
            validation_status=ValidationStatusChoices.VERIFIED,
            raw_text="Sample raw invoice text",
        )

        ext = InvoiceExtraction.objects.create(
            document=doc,
            invoice_number="INV-2024-999",
            invoice_date=date(2024, 6, 1),
            due_date=date(2024, 6, 30),
            supplier_name="Acme Global",
            supplier_address="100 Acme Way",
            customer_name="Client Corp",
            customer_address="200 Client Blvd",
            subtotal=Decimal("900.00"),
            tax=Decimal("90.00"),
            total=Decimal("990.00"),
            currency="USD",
            confidence_score=0.98,
            llm_model="gemini-1.5-flash",
        )

        LineItem.objects.create(
            extraction=ext,
            line_number=1,
            description="Cloud Hosting",
            quantity=Decimal("1.0000"),
            unit_price=Decimal("900.0000"),
            amount=Decimal("900.00"),
        )

        ValidationError.objects.create(
            document=doc,
            rule_id="MATH_SUBTOTAL_MATCH",
            field="subtotal",
            message="Subtotal matches line items.",
            severity=ValidationSeverityChoices.INFO,
        )

        AuditLog.objects.create(
            document=doc,
            user_id="operator_1",
            action="VERIFY",
            reason="Manual check passed",
        )

        response = client.get(f"/api/documents/{doc.id}/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data

        assert data["id"] == str(doc.id)
        assert data["filename"] == "detailed_inv.pdf"
        assert data["status"] == DocumentStatus.SUCCESS
        assert data["raw_text"] == "Sample raw invoice text"

        # Verify nested extraction
        extraction = data["extraction"]
        assert extraction["invoice_number"] == "INV-2024-999"
        assert extraction["total"] == "990.00"
        assert extraction["confidence_score"] == 0.98
        assert len(extraction["line_items"]) == 1
        assert extraction["line_items"][0]["description"] == "Cloud Hosting"

        # Verify nested validation errors
        assert len(data["validation_errors"]) == 1
        assert data["validation_errors"][0]["rule_id"] == "MATH_SUBTOTAL_MATCH"

        # Verify nested audit logs
        assert len(data["audit_logs"]) == 1
        assert data["audit_logs"][0]["action"] == "VERIFY"

    def test_get_document_detail_invalid_uuid(self, client):
        """Tests that querying with an invalid UUID string returns 400 Bad Request."""
        response = client.get("/api/documents/invalid-uuid-string/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data

    def test_get_document_detail_not_found(self, client):
        """Tests querying non-existent document UUID returns 404 Not Found."""
        random_id = str(uuid.uuid4())
        response = client.get(f"/api/documents/{random_id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# =========================================================================
# 4. Status Polling API Tests (GET /api/documents/{id}/status/)
# =========================================================================

class TestDocumentStatusAPI(BaseAPITest):
    """Verifies lightweight status polling endpoint for tracking progress."""

    def test_get_document_status(self, client):
        """Tests polling lightweight document processing status."""
        doc = Document.objects.create(
            filename="status_test.pdf",
            file_type="pdf",
            status=DocumentStatus.PROCESSING,
            validation_status=ValidationStatusChoices.PENDING,
        )

        response = client.get(f"/api/documents/{doc.id}/status/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data

        assert data["id"] == str(doc.id)
        assert data["status"] == DocumentStatus.PROCESSING
        assert data["validation_status"] == ValidationStatusChoices.PENDING
        assert data["error_message"] is None
        assert "raw_text" not in data  # Lightweight: does not include large fields


# =========================================================================
# 5. Document Reprocess / Retry API Tests (POST /api/documents/{id}/reprocess/)
# =========================================================================

class TestDocumentReprocessAPI(BaseAPITest):
    """Verifies retry and forced reprocessing semantics and concurrency guards."""

    def test_reprocess_failed_document_success(self, client):
        """Tests retrying a FAILED document initiates reprocessing."""
        doc = Document.objects.create(
            filename="failed_doc.pdf",
            file_type="pdf",
            status=DocumentStatus.FAILED,
            error_message="Temporary OCR timeout",
        )

        with patch("apps.documents.views.process_document_task.delay") as mock_task:
            response = client.post(f"/api/documents/{doc.id}/reprocess/", {}, format="json")

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data["document_id"] == str(doc.id)
        mock_task.assert_called_once_with(str(doc.id), force=False)

    def test_reprocess_success_document_without_force_rejected(self, client):
        """Tests that re-processing a SUCCESS document without force=true is rejected with 400."""
        doc = Document.objects.create(
            filename="done.pdf",
            file_type="pdf",
            status=DocumentStatus.SUCCESS,
            validation_status=ValidationStatusChoices.VERIFIED,
        )

        response = client.post(f"/api/documents/{doc.id}/reprocess/", {"force": False}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already been successfully processed" in response.data["error"]

    def test_reprocess_success_document_with_force_accepted(self, client):
        """Tests that re-processing a SUCCESS document with force=true is accepted."""
        doc = Document.objects.create(
            filename="done.pdf",
            file_type="pdf",
            status=DocumentStatus.SUCCESS,
            validation_status=ValidationStatusChoices.VERIFIED,
        )

        with patch("apps.documents.views.process_document_task.delay") as mock_task:
            response = client.post(f"/api/documents/{doc.id}/reprocess/", {"force": True}, format="json")

        assert response.status_code == status.HTTP_202_ACCEPTED
        mock_task.assert_called_once_with(str(doc.id), force=True)

    def test_reprocess_actively_processing_document_rejected(self, client):
        """Tests concurrency protection: requesting reprocessing on a PROCESSING doc returns 409 Conflict."""
        doc = Document.objects.create(
            filename="active.pdf",
            file_type="pdf",
            status=DocumentStatus.PROCESSING,
        )

        response = client.post(f"/api/documents/{doc.id}/reprocess/", {"force": True}, format="json")
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already being processed" in response.data["error"]


# =========================================================================
# 6. Cross-Document Reconciliation API Tests (POST/GET /api/reconciliations/)
# =========================================================================

class TestCrossReconciliationAPI(BaseAPITest):
    """Verifies cross-document verification trigger, validations, and result inspection."""

    def test_trigger_cross_reconciliation_success(self, client):
        """Tests triggering reconciliation between two valid documents."""
        doc_a = Document.objects.create(filename="inv_a.pdf", file_type="pdf", status=DocumentStatus.SUCCESS)
        InvoiceExtraction.objects.create(document=doc_a, invoice_number="INV-001", total=Decimal("100.00"))

        doc_b = Document.objects.create(filename="po_b.xlsx", file_type="xlsx", status=DocumentStatus.SUCCESS)
        InvoiceExtraction.objects.create(document=doc_b, invoice_number="INV-001", total=Decimal("100.00"))

        payload = {
            "doc_a_id": str(doc_a.id),
            "doc_b_id": str(doc_b.id),
            "tolerance": "0.05",
        }

        response = client.post("/api/reconciliations/", payload, format="json")
        # In eager mode, record is created immediately -> 201 Created
        assert response.status_code in (status.HTTP_201_CREATED, status.HTTP_202_ACCEPTED)

        if response.status_code == status.HTTP_201_CREATED:
            data = response.data
            assert data["doc_a"] == doc_a.id
            assert data["doc_b"] == doc_b.id
            assert data["is_reconciled"] is True

    def test_self_reconciliation_rejected(self, client):
        """Tests that attempting to reconcile a document against itself returns 400."""
        doc = Document.objects.create(filename="single.pdf", file_type="pdf")
        InvoiceExtraction.objects.create(document=doc, invoice_number="INV-1", total=Decimal("50.00"))

        payload = {
            "doc_a_id": str(doc.id),
            "doc_b_id": str(doc.id),
        }
        response = client.post("/api/reconciliations/", payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "self-reconciliation is not permitted" in str(response.data).lower()

    def test_reconciliation_missing_extraction_rejected(self, client):
        """Tests reconciling a document that lacks structured extraction returns 400."""
        doc_a = Document.objects.create(filename="doc_a.pdf", file_type="pdf")
        InvoiceExtraction.objects.create(document=doc_a, invoice_number="INV-1", total=Decimal("50.00"))

        doc_b = Document.objects.create(filename="unextracted.pdf", file_type="pdf")

        payload = {
            "doc_a_id": str(doc_a.id),
            "doc_b_id": str(doc_b.id),
        }
        response = client.post("/api/reconciliations/", payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "has not completed extraction" in str(response.data)

    def test_get_reconciliation_detail(self, client):
        """Tests retrieving a single CrossReconciliation record by ID."""
        doc_a = Document.objects.create(filename="a.pdf", file_type="pdf")
        doc_b = Document.objects.create(filename="b.pdf", file_type="pdf")

        rec = CrossReconciliation.objects.create(
            doc_a=doc_a,
            doc_b=doc_b,
            status=ValidationStatusChoices.VERIFIED,
            is_reconciled=True,
            discrepancies=[],
            warnings=[],
            fields_compared=["total", "invoice_number"],
            matched_items_count=2,
            unmatched_items_count=0,
            summary="Full reconciliation passed.",
        )

        response = client.get(f"/api/reconciliations/{rec.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(rec.id)
        assert response.data["is_reconciled"] is True
        assert response.data["summary"] == "Full reconciliation passed."
