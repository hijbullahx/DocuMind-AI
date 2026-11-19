"""
Comprehensive Test Suite for TASK-011: Celery Asynchronous Task Worker & Redis Integration.
Tests Celery application initialization, task auto-discovery, eager asynchronous execution,
end-to-end ingestion/extraction/validation pipeline coordination, database persistence,
idempotency guards, failure isolation, and cross-document reconciliation tasks.
"""
from datetime import date
from decimal import Decimal
import json
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch
import uuid

import django
import pytest

# Initialize Django & Celery test environment
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "documind.settings")
django.setup()

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management import call_command

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
from apps.documents.tasks import (
    DEFAULT_MOCK_INVOICE_JSON,
    process_document_task,
    reconcile_documents_task,
)
from apps.extraction.llm_client import MockLLMProvider
from documind.celery import app as celery_app


@pytest.fixture(scope="session", autouse=True)
def setup_celery_test_env():
    """Applies migrations once for the test session, isolates MEDIA_ROOT, and sets Celery eager mode."""
    call_command("migrate", verbosity=0)
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
    temp_media = tempfile.mkdtemp()
    settings.MEDIA_ROOT = temp_media
    yield
    shutil.rmtree(temp_media, ignore_errors=True)


@pytest.fixture(autouse=True)
def clean_celery_db():
    """Cleans up created test records between tests."""
    yield
    CrossReconciliation.objects.all().delete()
    AuditLog.objects.all().delete()
    ValidationError.objects.all().delete()
    LineItem.objects.all().delete()
    InvoiceExtraction.objects.all().delete()
    Document.objects.all().delete()


# =========================================================================
# 1. Celery Configuration & Discovery Tests
# =========================================================================

class TestCeleryConfiguration:
    """Verifies Celery application initialization, settings, and task discovery."""

    def test_celery_app_instance_and_name(self):
        assert celery_app.main == "documind"

    def test_celery_task_registration(self):
        registered_tasks = celery_app.tasks
        assert "apps.documents.tasks.process_document_task" in registered_tasks
        assert "apps.documents.tasks.reconcile_documents_task" in registered_tasks

    def test_celery_configuration_settings(self):
        assert settings.CELERY_ACCEPT_CONTENT == ["json"]
        assert settings.CELERY_TASK_SERIALIZER == "json"
        assert settings.CELERY_RESULT_SERIALIZER == "json"
        assert settings.CELERY_TASK_TIME_LIMIT == 300
        assert settings.CELERY_TASK_SOFT_TIME_LIMIT == 240
        assert settings.CELERY_TASK_ALWAYS_EAGER is True


# =========================================================================
# 2. Document Processing Pipeline Tests
# =========================================================================

class TestProcessDocumentTask:
    """Verifies process_document_task end-to-end execution, statuses, and database records."""

    def test_process_document_success_from_raw_text(self):
        """Tests successful end-to-end processing of a document with pre-populated raw text."""
        doc = Document.objects.create(
            filename="invoice_sample.txt",
            file_type="txt",
            raw_text="Invoice Number: INV-MOCK-001\nTotal: $110.00\nSubtotal: $100.00\nTax: $10.00",
            status=DocumentStatus.QUEUED,
        )

        res = process_document_task.delay(str(doc.id), provider="mock")
        result_data = res.get()

        assert result_data["success"] is True
        assert result_data["status"] == DocumentStatus.SUCCESS
        assert result_data["validation_status"] == ValidationStatusChoices.VERIFIED
        assert result_data["invoice_number"] == "INV-MOCK-001"

        # Check DB updates
        doc.refresh_from_db()
        assert doc.status == DocumentStatus.SUCCESS
        assert doc.validation_status == ValidationStatusChoices.VERIFIED
        assert doc.error_message is None

        # Check InvoiceExtraction persistence
        extraction = doc.extraction
        assert extraction.invoice_number == "INV-MOCK-001"
        assert extraction.supplier_name == "Mock Supplier LLC"
        assert extraction.total == Decimal("110.00")
        assert extraction.subtotal == Decimal("100.00")
        assert extraction.tax == Decimal("10.00")
        assert extraction.currency == "USD"
        assert extraction.confidence_score is not None

        # Check LineItem persistence
        items = list(extraction.line_items.all())
        assert len(items) == 1
        assert items[0].description == "Consulting Services"
        assert items[0].quantity == Decimal("2.0000")
        assert items[0].unit_price == Decimal("50.0000")
        assert items[0].amount == Decimal("100.00")

        # Check no validation errors
        assert doc.validation_errors.count() == 0

    def test_process_document_with_file_ingestion(self):
        """Tests processing a document with a CSV file attached, ingesting it and updating raw_text."""
        csv_content = b"Item,Qty,Price,Total\nConsulting Services,2,50,100\nSubtotal,,,100\nTax,,,10\nTotal,,,110\n"
        doc = Document.objects.create(
            filename="test_invoice.csv",
            file_type="csv",
            file=ContentFile(csv_content, name="test_invoice.csv"),
            status=DocumentStatus.QUEUED,
        )

        res = process_document_task.delay(str(doc.id), provider="mock")
        result_data = res.get()

        assert result_data["success"] is True
        doc.refresh_from_db()
        assert doc.status == DocumentStatus.SUCCESS
        assert "Consulting Services" in doc.raw_text
        assert doc.metadata.get("ingestion_status") == "SUCCESS"
        assert doc.extraction.total == Decimal("110.00")

    def test_process_document_validation_errors_detected(self):
        """Tests when extracted invoice has a math discrepancy, validation status becomes FAILED and errors are logged."""
        # Arithmetic mismatch: Subtotal 100 + Tax 10 != Total 150
        mismatch_invoice = json.dumps({
            "invoice_number": "INV-ERR-001",
            "invoice_date": "2024-05-01",
            "due_date": "2024-05-31",
            "supplier_name": "Discrepancy Corp",
            "supplier_address": "789 Err Road",
            "customer_name": "Target Client",
            "customer_address": "123 Client Way",
            "subtotal": "100.00",
            "tax": "10.00",
            "total": "150.00",  # Discrepancy: expected 110.00
            "currency": "USD",
            "line_items": [
                {
                    "description": "Erroneous Service",
                    "quantity": "1",
                    "unit_price": "100.00",
                    "amount": "100.00",
                }
            ],
            "raw_text_evidence": {
                "total": "150.00",
            },
        })

        doc = Document.objects.create(
            filename="bad_math_invoice.txt",
            file_type="txt",
            raw_text="Total $150.00 Subtotal $100.00 Tax $10.00",
            status=DocumentStatus.QUEUED,
        )

        res = process_document_task.delay(str(doc.id), provider="mock", canned_response=mismatch_invoice)
        result_data = res.get()

        assert result_data["success"] is True
        doc.refresh_from_db()
        # Validation detected the arithmetic error
        assert doc.validation_status == ValidationStatusChoices.FAILED
        assert doc.status == DocumentStatus.SUCCESS

        errors = list(doc.validation_errors.all())
        assert len(errors) >= 1
        tax_error = next((e for e in errors if e.rule_id == "MATH_TAX_ADDITION"), None)
        assert tax_error is not None
        assert tax_error.severity == ValidationSeverityChoices.ERROR
        assert tax_error.difference == Decimal("40.0000")

    def test_process_document_duplicate_invoice_anomaly(self):
        """Tests that processing a document with duplicate supplier and invoice_number triggers ANOMALY_DUPLICATE_INVOICE."""
        # 1. First document successfully processed
        doc1 = Document.objects.create(
            filename="orig_invoice.txt",
            file_type="txt",
            raw_text="Invoice INV-MOCK-001",
            status=DocumentStatus.QUEUED,
        )
        process_document_task.delay(str(doc1.id), provider="mock")

        # 2. Second document with identical supplier and invoice number
        doc2 = Document.objects.create(
            filename="duplicate_invoice.txt",
            file_type="txt",
            raw_text="Invoice INV-MOCK-001 duplicate",
            status=DocumentStatus.QUEUED,
        )
        res2 = process_document_task.delay(str(doc2.id), provider="mock")
        res2.get()

        doc2.refresh_from_db()
        assert doc2.validation_status == ValidationStatusChoices.FAILED

        dup_error = doc2.validation_errors.filter(rule_id="ANOMALY_DUPLICATE_INVOICE").first()
        assert dup_error is not None
        assert "Duplicate invoice detected" in dup_error.message
        assert dup_error.severity == ValidationSeverityChoices.ERROR

    def test_idempotency_guard_already_processing(self):
        """Tests that a task called on a document in PROCESSING status exits early unless forced."""
        doc = Document.objects.create(
            filename="active.pdf",
            file_type="pdf",
            status=DocumentStatus.PROCESSING,
        )

        res = process_document_task.delay(str(doc.id), force=False)
        result = res.get()

        assert result["success"] is False
        assert "already being processed" in result["message"]
        doc.refresh_from_db()
        assert doc.status == DocumentStatus.PROCESSING

    def test_idempotency_guard_already_success(self):
        """Tests that a task called on a document in SUCCESS status exits early unless forced."""
        doc = Document.objects.create(
            filename="done.pdf",
            file_type="pdf",
            status=DocumentStatus.SUCCESS,
            validation_status=ValidationStatusChoices.VERIFIED,
        )

        res = process_document_task.delay(str(doc.id), force=False)
        result = res.get()

        assert result["success"] is True
        assert "already been successfully processed" in result["message"]

    def test_force_reprocessing_creates_audit_log(self):
        """Tests that re-processing a document with force=True logs an AuditLog entry."""
        doc = Document.objects.create(
            filename="reprocess.txt",
            file_type="txt",
            raw_text="Invoice INV-MOCK-001 Total 110",
            status=DocumentStatus.SUCCESS,
            validation_status=ValidationStatusChoices.VERIFIED,
        )

        res = process_document_task.delay(str(doc.id), force=True, provider="mock")
        result = res.get()

        assert result["success"] is True
        doc.refresh_from_db()
        audit_entry = doc.audit_logs.filter(action="REPROCESS").first()
        assert audit_entry is not None
        assert audit_entry.user_id == "celery_worker"
        assert "previous status: SUCCESS" in audit_entry.reason

    def test_repeated_task_submission_idempotency(self):
        """Tests that submitting the same task twice processes it once and rejects the second as already SUCCESS."""
        doc = Document.objects.create(
            filename="repeat.txt",
            file_type="txt",
            raw_text="Invoice Number: INV-MOCK-001\nTotal: $110.00\nSubtotal: $100.00\nTax: $10.00",
            status=DocumentStatus.QUEUED,
        )

        res1 = process_document_task.delay(str(doc.id), provider="mock")
        res1_data = res1.get()
        assert res1_data["success"] is True
        assert res1_data["status"] == DocumentStatus.SUCCESS

        # Second submission of identical task
        res2 = process_document_task.delay(str(doc.id), provider="mock")
        res2_data = res2.get()
        assert res2_data["success"] is True
        assert "already been successfully processed" in res2_data["message"]

    def test_atomic_claim_competing_worker_rejected(self):
        """Tests that if a competing worker transitions a QUEUED document to PROCESSING before claim, this worker is rejected."""
        doc = Document.objects.create(
            filename="compete.txt",
            file_type="txt",
            raw_text="Invoice Number: INV-MOCK-001\nTotal: $110.00",
            status=DocumentStatus.QUEUED,
        )

        real_filter = Document.objects.filter

        def custom_filter(*args, **kwargs):
            qs = real_filter(*args, **kwargs)
            # If filtering with status__in=[DocumentStatus.QUEUED], simulate competing worker already claimed it
            if "status__in" in kwargs:
                Document.objects.filter(id=doc.id).update(status=DocumentStatus.PROCESSING)
            return qs

        with patch("apps.documents.tasks.Document.objects.filter", side_effect=custom_filter):
            res = process_document_task.delay(str(doc.id), provider="mock")
            result = res.get()

        assert result["success"] is False
        assert result["status"] == DocumentStatus.PROCESSING
        assert "already being processed" in result["message"]

    def test_forced_reprocessing_active_processing_rejected(self):
        """Tests that force=True cannot claim or interrupt a document that is actively in PROCESSING status."""
        doc = Document.objects.create(
            filename="active_reprocess.pdf",
            file_type="pdf",
            status=DocumentStatus.PROCESSING,
        )

        res = process_document_task.delay(str(doc.id), force=True, provider="mock")
        result = res.get()

        assert result["success"] is False
        assert result["status"] == DocumentStatus.PROCESSING
        assert "already being processed" in result["message"]
        assert doc.audit_logs.count() == 0

    def test_forced_reprocessing_competing_claim_rejected(self):
        """Tests that if another worker claims a force=True document first, the competing worker is rejected."""
        doc = Document.objects.create(
            filename="forced_compete.txt",
            file_type="txt",
            raw_text="Invoice Number: INV-MOCK-001\nTotal: $110.00",
            status=DocumentStatus.SUCCESS,
            validation_status=ValidationStatusChoices.VERIFIED,
        )

        real_filter = Document.objects.filter

        def custom_filter(*args, **kwargs):
            qs = real_filter(*args, **kwargs)
            class InterceptedQuerySet:
                def __init__(self, inner):
                    self.inner = inner
                def exclude(self, *e_args, **e_kwargs):
                    Document.objects.filter(id=doc.id).update(status=DocumentStatus.PROCESSING)
                    return self.inner.exclude(*e_args, **e_kwargs)
                def __getattr__(self, name):
                    return getattr(self.inner, name)

            if kwargs.get("id") == doc.id and "status__in" not in kwargs:
                return InterceptedQuerySet(qs)
            return qs

        with patch("apps.documents.tasks.Document.objects.filter", side_effect=custom_filter):
            res = process_document_task.delay(str(doc.id), force=True, provider="mock")
            result = res.get()

        assert result["success"] is False
        assert "already being processed" in result["message"]
        assert doc.audit_logs.count() == 0

    def test_failure_handling_transitions_to_failed_without_stuck_processing(self):
        """Tests that an exception during processing transitions status to FAILED and does not leave document stuck."""
        doc = Document.objects.create(
            filename="crash.txt",
            file_type="txt",
            raw_text="Valid invoice text",
            status=DocumentStatus.QUEUED,
        )

        with patch("apps.documents.tasks.LLMExtractionClient.extract", side_effect=ValueError("Non-retryable extraction error")):
            res = process_document_task.delay(str(doc.id), provider="mock")
            result = res.get()

        assert result["success"] is False
        doc.refresh_from_db()
        assert doc.status == DocumentStatus.FAILED
        assert doc.validation_status == ValidationStatusChoices.FAILED
        assert "Non-retryable extraction error" in doc.error_message

    def test_nonexistent_document_id(self):
        """Tests graceful handling when document ID does not exist."""
        random_id = str(uuid.uuid4())
        res = process_document_task.delay(random_id)
        result = res.get()

        assert result["success"] is False
        assert f"Document {random_id} not found" in result["error"]

    def test_invalid_uuid_handling(self):
        """Tests graceful handling of malformed UUID string."""
        res = process_document_task.delay("not-a-valid-uuid")
        result = res.get()

        assert result["success"] is False
        assert "error" in result

    def test_empty_content_failure(self):
        """Tests that document with no file and no raw_text fails gracefully."""
        doc = Document.objects.create(
            filename="empty.pdf",
            file_type="pdf",
            status=DocumentStatus.QUEUED,
        )

        res = process_document_task.delay(str(doc.id))
        result = res.get()

        assert result["success"] is False
        doc.refresh_from_db()
        assert doc.status == DocumentStatus.FAILED
        assert doc.validation_status == ValidationStatusChoices.FAILED
        assert "neither an attached file nor raw_text" in doc.error_message

    def test_process_document_corrupted_file(self):
        """Tests that a corrupted file attached to document fails gracefully with FAILED status."""
        corrupt_bytes = b"NOT_A_VALID_DOCUMENT_CORRUPTED_STREAM"
        doc = Document.objects.create(
            filename="corrupt.xyz",
            file_type="xyz",
            file=ContentFile(corrupt_bytes, name="corrupt.xyz"),
            status=DocumentStatus.QUEUED,
        )

        res = process_document_task.delay(str(doc.id), provider="mock")
        result = res.get()

        assert result["success"] is False
        doc.refresh_from_db()
        assert doc.status == DocumentStatus.FAILED
        assert doc.validation_status == ValidationStatusChoices.FAILED
        assert "Unsupported" in doc.error_message or "failed" in doc.error_message.lower()

    def test_process_document_pdf_file_ingestion(self):
        """Tests processing a real PDF document through file ingestion and extraction."""
        import pymupdf as fitz
        fitz_doc = fitz.open()
        page = fitz_doc.new_page()
        page.insert_text((72, 72), "Invoice INV-MOCK-001\nTotal: $110.00\nSubtotal: $100.00\nTax: $10.00")
        pdf_bytes = fitz_doc.tobytes()
        fitz_doc.close()

        doc = Document.objects.create(
            filename="digital_invoice.pdf",
            file_type="pdf",
            file=ContentFile(pdf_bytes, name="digital_invoice.pdf"),
            status=DocumentStatus.QUEUED,
        )

        res = process_document_task.delay(str(doc.id), provider="mock")
        result = res.get()

        assert result["success"] is True
        doc.refresh_from_db()
        assert doc.status == DocumentStatus.SUCCESS
        assert doc.page_count >= 1
        assert "INV-MOCK-001" in doc.raw_text
        assert doc.extraction.total == Decimal("110.00")


# =========================================================================
# 3. Cross-Document Reconciliation Task Tests
# =========================================================================

class TestReconcileDocumentsTask:
    """Verifies reconcile_documents_task asynchronous execution and database persistence."""

    def test_reconcile_matching_documents(self):
        """Tests successful reconciliation between two matching documents."""
        # Document A
        doc_a = Document.objects.create(
            filename="invoice_po.pdf",
            file_type="pdf",
            status=DocumentStatus.SUCCESS,
            validation_status=ValidationStatusChoices.VERIFIED,
        )
        ext_a = InvoiceExtraction.objects.create(
            document=doc_a,
            invoice_number="INV-2024-100",
            invoice_date=date(2024, 6, 1),
            supplier_name="Global Tech Supply",
            total=Decimal("500.00"),
            subtotal=Decimal("450.00"),
            tax=Decimal("50.00"),
            currency="USD",
        )
        LineItem.objects.create(
            extraction=ext_a,
            line_number=1,
            description="Network Switch",
            quantity=Decimal("1"),
            unit_price=Decimal("450.00"),
            amount=Decimal("450.00"),
        )

        # Document B (Matching PO / Ledger)
        doc_b = Document.objects.create(
            filename="po_record.xlsx",
            file_type="xlsx",
            status=DocumentStatus.SUCCESS,
            validation_status=ValidationStatusChoices.VERIFIED,
        )
        ext_b = InvoiceExtraction.objects.create(
            document=doc_b,
            invoice_number="INV-2024-100",
            invoice_date=date(2024, 6, 1),
            supplier_name="Global Tech Supply",
            total=Decimal("500.00"),
            subtotal=Decimal("450.00"),
            tax=Decimal("50.00"),
            currency="USD",
        )
        LineItem.objects.create(
            extraction=ext_b,
            line_number=1,
            description="Network Switch",
            quantity=Decimal("1"),
            unit_price=Decimal("450.00"),
            amount=Decimal("450.00"),
        )

        res = reconcile_documents_task.delay(str(doc_a.id), str(doc_b.id))
        result = res.get()

        assert result["success"] is True
        assert result["is_reconciled"] is True
        assert result["status"] == ValidationStatusChoices.VERIFIED
        assert result["discrepancies_count"] == 0

        # Verify CrossReconciliation model in DB
        reconciliation = CrossReconciliation.objects.get(id=result["reconciliation_id"])
        assert reconciliation.doc_a == doc_a
        assert reconciliation.doc_b == doc_b
        assert reconciliation.is_reconciled is True
        assert reconciliation.matched_items_count == 1
        assert reconciliation.unmatched_items_count == 0

    def test_reconcile_mismatching_documents(self):
        """Tests cross-reconciliation detecting financial discrepancies between documents."""
        doc_a = Document.objects.create(
            filename="inv_a.pdf",
            file_type="pdf",
            status=DocumentStatus.SUCCESS,
        )
        InvoiceExtraction.objects.create(
            document=doc_a,
            invoice_number="PO-999",
            supplier_name="Alpha Corp",
            total=Decimal("1000.00"),
        )

        doc_b = Document.objects.create(
            filename="inv_b.pdf",
            file_type="pdf",
            status=DocumentStatus.SUCCESS,
        )
        InvoiceExtraction.objects.create(
            document=doc_b,
            invoice_number="PO-999",
            supplier_name="Alpha Corp",
            total=Decimal("1200.00"),  # $200 discrepancy
        )

        res = reconcile_documents_task.delay(str(doc_a.id), str(doc_b.id))
        result = res.get()

        assert result["success"] is True
        assert result["is_reconciled"] is False
        assert result["status"] == ValidationStatusChoices.FAILED
        assert result["discrepancies_count"] >= 1

        rec = CrossReconciliation.objects.get(id=result["reconciliation_id"])
        assert rec.is_reconciled is False
        assert len(rec.discrepancies) >= 1
        total_disc = next((d for d in rec.discrepancies if d.get("field") == "total"), None)
        assert total_disc is not None
        assert total_disc["doc_a_value"] == "1000.00"
        assert total_disc["doc_b_value"] == "1200.00"

    def test_reconcile_self_reconciliation_prevented(self):
        """Tests that attempting to reconcile a document against itself is rejected gracefully."""
        doc = Document.objects.create(filename="same.pdf", file_type="pdf")
        res = reconcile_documents_task.delay(str(doc.id), str(doc.id))
        result = res.get()

        assert result["success"] is False
        assert "self-reconciliation is not permitted" in result["error"]
        assert CrossReconciliation.objects.count() == 0

    def test_reconcile_missing_extraction_rejected(self):
        """Tests that reconciling a document that lacks an extraction record fails gracefully."""
        doc_a = Document.objects.create(filename="has_ext.pdf", file_type="pdf")
        InvoiceExtraction.objects.create(document=doc_a, invoice_number="INV-1", total=Decimal("100.00"))

        doc_b = Document.objects.create(filename="no_ext.pdf", file_type="pdf")

        res = reconcile_documents_task.delay(str(doc_a.id), str(doc_b.id))
        result = res.get()

        assert result["success"] is False
        assert "has no structured extraction record" in result["error"]

    def test_reconcile_nonexistent_documents(self):
        """Tests that reconciling non-existent document IDs fails gracefully."""
        rand_a = str(uuid.uuid4())
        rand_b = str(uuid.uuid4())
        res = reconcile_documents_task.delay(rand_a, rand_b)
        result = res.get()

        assert result["success"] is False
        assert f"Document A ({rand_a}) not found" in result["error"]
