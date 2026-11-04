"""
Comprehensive test suite for TASK-010: Django Database Models & Migrations.
Tests Document, InvoiceExtraction, LineItem, ValidationError, AuditLog, and CrossReconciliation models,
including UUID keys, Decimal financial precision, cascade deletion, JSON fields, and migration integrity.
"""
from datetime import date
from decimal import Decimal
import os
import uuid
import pytest

import django
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.management import call_command
from django.db import connection, IntegrityError

# Initialize Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'documind.settings')
django.setup()

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
from apps.extraction.schemas import InvoiceExtraction as PydanticInvoice, LineItemExtraction as PydanticLineItem
from apps.validation.models import ValidationError as PydanticValidationError, ValidationResult as PydanticValidationResult, ValidationSeverity, ValidationStatus
from apps.validation.cross_verifier import CrossVerificationResult as PydanticCrossResult, CrossDocumentDiscrepancy


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Applies migrations once for the test session."""
    call_command("migrate", verbosity=0)
    yield


@pytest.fixture(autouse=True)
def clean_db():
    """Cleans up created test records between tests."""
    yield
    CrossReconciliation.objects.all().delete()
    AuditLog.objects.all().delete()
    ValidationError.objects.all().delete()
    LineItem.objects.all().delete()
    InvoiceExtraction.objects.all().delete()
    Document.objects.all().delete()


# =========================================================================
# 1. Document Model Tests
# =========================================================================

class TestDocumentModel:
    """Verifies Document lifecycle, defaults, UUIDs, metadata, and status tracking."""

    def test_document_creation_with_defaults(self):
        doc = Document.objects.create(
            filename="invoice_1001.pdf",
            file_type="pdf",
            file_size_bytes=102400,
            page_count=2,
        )

        assert isinstance(doc.id, uuid.UUID)
        assert doc.status == DocumentStatus.QUEUED
        assert doc.validation_status == ValidationStatusChoices.PENDING
        assert doc.created_at is not None
        assert doc.updated_at is not None
        assert "invoice_1001.pdf" in str(doc)

    def test_document_json_metadata_storage(self):
        meta_payload = {
            "author": "Acme Corp",
            "sheet_names": ["Sheet1", "Summary"],
            "ocr_warnings": ["Page 2 low contrast"],
        }
        doc = Document.objects.create(
            filename="sheet_2026.xlsx",
            file_type="xlsx",
            metadata=meta_payload,
        )

        fetched = Document.objects.get(id=doc.id)
        assert fetched.metadata["author"] == "Acme Corp"
        assert fetched.metadata["sheet_names"] == ["Sheet1", "Summary"]
        assert fetched.metadata["ocr_warnings"] == ["Page 2 low contrast"]

    def test_document_status_transitions(self):
        doc = Document.objects.create(filename="test.pdf", file_type="pdf")
        doc.status = DocumentStatus.PROCESSING
        doc.save()
        assert Document.objects.get(id=doc.id).status == DocumentStatus.PROCESSING

        doc.status = DocumentStatus.SUCCESS
        doc.validation_status = ValidationStatusChoices.VERIFIED
        doc.save()
        fetched = Document.objects.get(id=doc.id)
        assert fetched.status == DocumentStatus.SUCCESS
        assert fetched.validation_status == ValidationStatusChoices.VERIFIED

    def test_document_clean_validation_detects_invalid_status(self):
        doc = Document(filename="bad_status.pdf", file_type="pdf", status="NON_EXISTENT_STATUS")
        with pytest.raises(DjangoValidationError) as exc_info:
            doc.full_clean()
        assert "status" in exc_info.value.message_dict

        with pytest.raises(DjangoValidationError):
            doc.save()

    def test_document_invalid_validation_status_rejected_on_save(self):
        doc = Document.objects.create(filename="valid.pdf", file_type="pdf")
        doc.validation_status = "INVALID_VAL_STATUS"
        with pytest.raises(DjangoValidationError):
            doc.save()

    def test_document_update_without_status_change_succeeds(self):
        doc = Document.objects.create(filename="test_update.pdf", file_type="pdf", status=DocumentStatus.QUEUED)
        doc.raw_text = "Extracted invoice content here"
        doc.error_message = "Minor warning recorded"
        doc.page_count = 5
        doc.save()

        fetched = Document.objects.get(id=doc.id)
        assert fetched.raw_text == "Extracted invoice content here"
        assert fetched.error_message == "Minor warning recorded"
        assert fetched.page_count == 5
        assert fetched.status == DocumentStatus.QUEUED


# =========================================================================
# 2. InvoiceExtraction & LineItem Model Tests
# =========================================================================

class TestInvoiceExtractionAndLineItems:
    """Verifies relational extraction storage, Decimal precision, and cascade deletion."""

    def test_invoice_extraction_creation_and_one_to_one(self):
        doc = Document.objects.create(filename="invoice.pdf", file_type="pdf")
        extraction = InvoiceExtraction.objects.create(
            document=doc,
            invoice_number="INV-2026-999",
            invoice_date=date(2026, 5, 1),
            due_date=date(2026, 6, 1),
            supplier_name="Apex Industrial Supplies LLC",
            customer_name="Omega Logistics Corp",
            subtotal=Decimal("900.00"),
            tax=Decimal("90.00"),
            total=Decimal("990.00"),
            currency="USD",
            raw_text_evidence={"total": "Total: $990.00"},
            confidence_score=0.98,
            llm_model="gpt-4o",
        )

        assert extraction.id is not None
        assert doc.extraction == extraction
        assert extraction.subtotal == Decimal("900.00")
        assert extraction.tax == Decimal("90.00")
        assert extraction.total == Decimal("990.00")
        assert extraction.raw_text_evidence["total"] == "Total: $990.00"

    def test_invoice_extraction_one_to_one_unique_enforcement(self):
        doc = Document.objects.create(filename="dup_ext.pdf", file_type="pdf")
        InvoiceExtraction.objects.create(document=doc, invoice_number="INV-1", total=Decimal("100.00"))

        with pytest.raises(IntegrityError):
            InvoiceExtraction.objects.create(document=doc, invoice_number="INV-2", total=Decimal("200.00"))

    def test_zero_hallucination_null_fields_allowed(self):
        doc = Document.objects.create(filename="sparse_invoice.pdf", file_type="pdf")
        extraction = InvoiceExtraction.objects.create(
            document=doc,
            invoice_number=None,
            invoice_date=None,
            due_date=None,
            supplier_name=None,
            customer_name=None,
            subtotal=None,
            tax=None,
            total=None,
            currency=None,
        )

        fetched = InvoiceExtraction.objects.get(id=extraction.id)
        assert fetched.invoice_number is None
        assert fetched.total is None
        assert fetched.supplier_name is None

    def test_line_items_foreign_key_and_ordering(self):
        doc = Document.objects.create(filename="multi_item.pdf", file_type="pdf")
        extraction = InvoiceExtraction.objects.create(document=doc, total=Decimal("500.00"))

        item1 = LineItem.objects.create(
            extraction=extraction,
            line_number=1,
            description="Steel Flange",
            quantity=Decimal("2.0000"),
            unit_price=Decimal("100.0000"),
            amount=Decimal("200.00"),
        )
        item2 = LineItem.objects.create(
            extraction=extraction,
            line_number=2,
            description="Control Valve",
            quantity=Decimal("3.0000"),
            unit_price=Decimal("100.0000"),
            amount=Decimal("300.00"),
        )

        items = list(extraction.line_items.all())
        assert len(items) == 2
        assert items[0] == item1
        assert items[1] == item2
        assert items[0].quantity == Decimal("2.0000")
        assert items[0].amount == Decimal("200.00")

    def test_cascade_delete_document_removes_extraction_and_items(self):
        doc = Document.objects.create(filename="doomed.pdf", file_type="pdf")
        extraction = InvoiceExtraction.objects.create(document=doc, total=Decimal("100.00"))
        LineItem.objects.create(
            extraction=extraction,
            description="Item to be deleted",
            amount=Decimal("100.00"),
        )

        ext_id = extraction.id
        doc.delete()

        assert not InvoiceExtraction.objects.filter(id=ext_id).exists()
        assert not LineItem.objects.filter(extraction_id=ext_id).exists()


# =========================================================================
# 3. ValidationError Model Tests
# =========================================================================

class TestValidationErrorModel:
    """Verifies persistence of validation findings and dismissal workflows."""

    def test_validation_error_creation(self):
        doc = Document.objects.create(filename="invalid.pdf", file_type="pdf")
        err = ValidationError.objects.create(
            document=doc,
            rule_id="LINE_ITEM_SUM_MISMATCH",
            field="subtotal",
            message="Sum of line items (100.00) differs from subtotal (120.00).",
            severity=ValidationSeverityChoices.ERROR,
            actual_value="100.00",
            expected_value="120.00",
            difference=Decimal("20.00"),
        )

        assert err.id is not None
        assert err.document == doc
        assert err.severity == ValidationSeverityChoices.ERROR
        assert err.difference == Decimal("20.00")
        assert not err.is_dismissed

    def test_validation_error_dismissal(self):
        doc = Document.objects.create(filename="warning.pdf", file_type="pdf")
        warning = ValidationError.objects.create(
            document=doc,
            rule_id="FUTURE_DATE_WARNING",
            field="invoice_date",
            message="Invoice date is in the future.",
            severity=ValidationSeverityChoices.WARNING,
        )

        warning.is_dismissed = True
        warning.dismissed_by = "operator_alice"
        warning.save()

        fetched = ValidationError.objects.get(id=warning.id)
        assert fetched.is_dismissed is True
        assert fetched.dismissed_by == "operator_alice"

    def test_validation_error_dismiss_method(self):
        doc = Document.objects.create(filename="warn2.pdf", file_type="pdf")
        err = ValidationError.objects.create(
            document=doc,
            rule_id="RULE_TEST",
            field="subtotal",
            message="Check",
            severity=ValidationSeverityChoices.WARNING,
        )

        err.dismiss("operator_bob")
        fetched = ValidationError.objects.get(id=err.id)
        assert fetched.is_dismissed is True
        assert fetched.dismissed_by == "operator_bob"
        assert fetched.dismissed_at is not None

    def test_cascade_delete_document_removes_validation_errors(self):
        doc = Document.objects.create(filename="doc.pdf", file_type="pdf")
        ValidationError.objects.create(
            document=doc,
            rule_id="RULE_A",
            field="total",
            message="Test error",
        )

        doc_id = doc.id
        doc.delete()
        assert not ValidationError.objects.filter(document_id=doc_id).exists()


# =========================================================================
# 4. AuditLog Model Tests
# =========================================================================

class TestAuditLogModel:
    """Verifies immutable audit trail recording."""

    def test_audit_log_entry_creation(self):
        doc = Document.objects.create(filename="audit_target.pdf", file_type="pdf")
        log = AuditLog.objects.create(
            document=doc,
            user_id="operator_bob",
            action="MANUAL_CORRECTION",
            field_name="total",
            old_value="900.00",
            new_value="1000.00",
            reason="OCR misread 1 as 0; corrected per invoice visual.",
        )

        assert log.id is not None
        assert log.document == doc
        assert log.user_id == "operator_bob"
        assert log.action == "MANUAL_CORRECTION"
        assert log.created_at is not None

    def test_audit_log_immutability_blocks_modification(self):
        doc = Document.objects.create(filename="immutable_test.pdf", file_type="pdf")
        log = AuditLog.objects.create(
            document=doc,
            user_id="operator_charlie",
            action="DISMISS_WARNING",
            field_name="tax",
            old_value="ERROR",
            new_value="DISMISSED",
            reason="Verified tax exemption certificate.",
        )

        log.reason = "Altered after the fact"
        with pytest.raises(PermissionError) as exc_info:
            log.save()
        assert "immutable" in str(exc_info.value).lower()

    def test_audit_log_immutability_blocks_direct_deletion(self):
        doc = Document.objects.create(filename="immutable_del.pdf", file_type="pdf")
        log = AuditLog.objects.create(
            document=doc,
            action="CRITICAL_EVENT",
        )

        with pytest.raises(PermissionError) as exc_info:
            log.delete()
        assert "immutable" in str(exc_info.value).lower()

    def test_audit_logs_cascade_with_document(self):
        doc = Document.objects.create(filename="temp.pdf", file_type="pdf")
        AuditLog.objects.create(
            document=doc,
            action="STATUS_CHANGE",
            reason="Test",
        )
        doc_id = doc.id
        doc.delete()
        assert not AuditLog.objects.filter(document_id=doc_id).exists()


# =========================================================================
# 5. CrossReconciliation Model Tests
# =========================================================================

class TestCrossReconciliationModel:
    """Verifies two-document cross-verification persistence."""

    def test_cross_reconciliation_creation(self):
        doc_a = Document.objects.create(filename="invoice.pdf", file_type="pdf")
        doc_b = Document.objects.create(filename="purchase_order.pdf", file_type="pdf")

        recon = CrossReconciliation.objects.create(
            doc_a=doc_a,
            doc_b=doc_b,
            status=ValidationStatusChoices.VERIFIED,
            is_reconciled=True,
            discrepancies=[],
            warnings=[],
            fields_compared=["total", "currency", "line_items"],
            matched_items_count=3,
            unmatched_items_count=0,
            summary="All 3 line items matched identically.",
        )

        assert recon.id is not None
        assert recon.doc_a == doc_a
        assert recon.doc_b == doc_b
        assert recon.is_reconciled is True
        assert recon.matched_items_count == 3
        assert doc_a.reconciliations_as_a.count() == 1
        assert doc_b.reconciliations_as_b.count() == 1

    def test_cross_reconciliation_stores_discrepancies_json(self):
        doc_a = Document.objects.create(filename="inv.pdf", file_type="pdf")
        doc_b = Document.objects.create(filename="po.pdf", file_type="pdf")

        disc_list = [
            {
                "rule_id": "CROSS_TOTAL_MISMATCH",
                "field": "total",
                "message": "Total mismatch between doc_a (1000.00) and doc_b (950.00)",
                "difference": "50.00",
            }
        ]

        recon = CrossReconciliation.objects.create(
            doc_a=doc_a,
            doc_b=doc_b,
            status=ValidationStatusChoices.FAILED,
            is_reconciled=False,
            discrepancies=disc_list,
        )

        fetched = CrossReconciliation.objects.get(id=recon.id)
        assert len(fetched.discrepancies) == 1
        assert fetched.discrepancies[0]["rule_id"] == "CROSS_TOTAL_MISMATCH"

    def test_deleting_either_document_cascades_reconciliation(self):
        doc_a = Document.objects.create(filename="a.pdf", file_type="pdf")
        doc_b = Document.objects.create(filename="b.pdf", file_type="pdf")
        recon = CrossReconciliation.objects.create(doc_a=doc_a, doc_b=doc_b)

        recon_id = recon.id
        doc_a.delete()
        assert not CrossReconciliation.objects.filter(id=recon_id).exists()

    def test_cross_reconciliation_prevents_self_reconciliation(self):
        doc = Document.objects.create(filename="self.pdf", file_type="pdf")
        recon = CrossReconciliation(doc_a=doc, doc_b=doc)

        with pytest.raises(DjangoValidationError) as exc_info:
            recon.full_clean()
        assert "doc_b" in exc_info.value.message_dict

        with pytest.raises(DjangoValidationError):
            recon.save()


# =========================================================================
# 6. Integration Compatibility with Previous Tasks
# =========================================================================

class TestIntegrationWithPreviousTasks:
    """Verifies that Pydantic outputs from TASK-006, 008, 009 cleanly map to Django models."""

    def test_pydantic_invoice_extraction_persists_to_django(self):
        # TASK-006 Pydantic schema instance
        pydantic_inv = PydanticInvoice(
            invoice_number="INV-2026-X",
            invoice_date="2026-04-15",
            supplier_name="Global Fasteners Inc.",
            total=Decimal("450.00"),
            subtotal=Decimal("400.00"),
            tax=Decimal("50.00"),
            currency="USD",
            line_items=[
                PydanticLineItem(description="Bolt M8", quantity=Decimal("100"), unit_price=Decimal("2.00"), amount=Decimal("200.00")),
                PydanticLineItem(description="Nut M8", quantity=Decimal("100"), unit_price=Decimal("2.00"), amount=Decimal("200.00")),
            ],
            raw_text_evidence={"total": "$450.00"},
        )

        doc = Document.objects.create(filename="fasteners.pdf", file_type="pdf")
        db_extraction = InvoiceExtraction.objects.create(
            document=doc,
            invoice_number=pydantic_inv.invoice_number,
            invoice_date=pydantic_inv.invoice_date,
            supplier_name=pydantic_inv.supplier_name,
            total=pydantic_inv.total,
            subtotal=pydantic_inv.subtotal,
            tax=pydantic_inv.tax,
            currency=pydantic_inv.currency,
            raw_text_evidence=pydantic_inv.raw_text_evidence,
        )

        for idx, item in enumerate(pydantic_inv.line_items, start=1):
            LineItem.objects.create(
                extraction=db_extraction,
                line_number=idx,
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price,
                amount=item.amount,
            )

        assert doc.extraction.total == Decimal("450.00")
        assert doc.extraction.line_items.count() == 2

    def test_pydantic_validation_result_persists_to_django(self):
        # TASK-008 Pydantic validation error instance
        pydantic_err = PydanticValidationError(
            rule_id="TAX_CALCULATION_MISMATCH",
            field="tax",
            message="Calculated subtotal + tax does not equal total.",
            severity=ValidationSeverity.ERROR,
            actual="50.00",
            expected="40.00",
            difference=Decimal("10.00"),
        )

        doc = Document.objects.create(filename="tax_err.pdf", file_type="pdf")
        db_err = ValidationError.objects.create(
            document=doc,
            rule_id=pydantic_err.rule_id,
            field=pydantic_err.field,
            message=pydantic_err.message,
            severity=pydantic_err.severity.value,
            actual_value=pydantic_err.actual,
            expected_value=pydantic_err.expected,
            difference=pydantic_err.difference,
        )

        assert db_err.rule_id == "TAX_CALCULATION_MISMATCH"
        assert db_err.difference == Decimal("10.00")
        assert db_err.severity == "ERROR"

    def test_pydantic_cross_verification_persists_to_django(self):
        # TASK-009 Pydantic cross verification result
        pydantic_res = PydanticCrossResult(
            status=ValidationStatus.NEEDS_REVIEW,
            is_reconciled=False,
            doc_a_id="invoice.pdf",
            doc_b_id="po.pdf",
            discrepancies=[],
            warnings=[
                CrossDocumentDiscrepancy(
                    rule_id="CROSS_REFERENCE_MISMATCH",
                    field="invoice_number",
                    message="PO reference differs from invoice number.",
                    severity=ValidationSeverity.WARNING,
                    doc_a_value="INV-001",
                    doc_b_value="PO-999",
                )
            ],
            fields_compared=["total", "invoice_number"],
            matched_items_count=2,
            unmatched_items_count=0,
            summary="Review needed: reference mismatch.",
        )

        doc_a = Document.objects.create(filename="invoice.pdf", file_type="pdf")
        doc_b = Document.objects.create(filename="po.pdf", file_type="pdf")

        db_recon = CrossReconciliation.objects.create(
            doc_a=doc_a,
            doc_b=doc_b,
            status=pydantic_res.status.value,
            is_reconciled=pydantic_res.is_reconciled,
            discrepancies=[d.to_dict() for d in pydantic_res.discrepancies],
            warnings=[w.to_dict() for w in pydantic_res.warnings],
            fields_compared=pydantic_res.fields_compared,
            matched_items_count=pydantic_res.matched_items_count,
            unmatched_items_count=pydantic_res.unmatched_items_count,
            summary=pydantic_res.summary,
        )

        assert db_recon.status == "NEEDS_REVIEW"
        assert len(db_recon.warnings) == 1
        assert db_recon.warnings[0]["rule_id"] == "CROSS_REFERENCE_MISMATCH"


# =========================================================================
# 7. Model Representations, Constraints, and Querying
# =========================================================================

class TestModelRepresentationAndConstraints:
    """Verifies string representations, filtering, and model constraints."""

    def test_model_string_representations(self):
        doc = Document.objects.create(filename="sample_invoice.pdf", file_type="pdf")
        assert "sample_invoice.pdf" in str(doc)

        ext = InvoiceExtraction.objects.create(
            document=doc,
            invoice_number="INV-42",
            total=Decimal("123.45"),
            currency="USD",
        )
        assert "INV-42" in str(ext)
        assert "123.45" in str(ext)

        item = LineItem.objects.create(
            extraction=ext,
            line_number=1,
            description="Premium Widget",
            amount=Decimal("123.45"),
        )
        assert "Line 1" in str(item)
        assert "Premium Widget" in str(item)

        err = ValidationError.objects.create(
            document=doc,
            rule_id="TEST_RULE",
            field="total",
            message="Test discrepancy",
            severity=ValidationSeverityChoices.ERROR,
        )
        assert "[ERROR]" in str(err)
        assert "TEST_RULE" in str(err)

        log = AuditLog.objects.create(
            document=doc,
            user_id="alice",
            action="TEST_ACTION",
        )
        assert "TEST_ACTION" in str(log)
        assert "alice" in str(log)

        doc_b = Document.objects.create(filename="sample_po.pdf", file_type="pdf")
        recon = CrossReconciliation.objects.create(
            doc_a=doc,
            doc_b=doc_b,
            status=ValidationStatusChoices.VERIFIED,
        )
        assert "Reconciliation" in str(recon)
        assert "sample_invoice.pdf" in str(recon)
        assert "sample_po.pdf" in str(recon)

    def test_document_filtering_by_status_and_validation(self):
        d1 = Document.objects.create(
            filename="d1.pdf",
            file_type="pdf",
            status=DocumentStatus.SUCCESS,
            validation_status=ValidationStatusChoices.VERIFIED,
        )
        d2 = Document.objects.create(
            filename="d2.pdf",
            file_type="pdf",
            status=DocumentStatus.FAILED,
            validation_status=ValidationStatusChoices.FAILED,
        )
        d3 = Document.objects.create(
            filename="d3.pdf",
            file_type="pdf",
            status=DocumentStatus.SUCCESS,
            validation_status=ValidationStatusChoices.NEEDS_REVIEW,
        )

        verified = Document.objects.filter(validation_status=ValidationStatusChoices.VERIFIED)
        assert verified.count() == 1
        assert verified.first() == d1

        failed = Document.objects.filter(status=DocumentStatus.FAILED)
        assert failed.count() == 1
        assert failed.first() == d2

        needs_review = Document.objects.filter(validation_status=ValidationStatusChoices.NEEDS_REVIEW)
        assert needs_review.count() == 1
        assert needs_review.first() == d3

    def test_migration_reproducibility(self):
        """Verifies no uncommitted schema changes exist."""
        from django.core.management import call_command
        # makemigrations --check will exit with 0 if no models need migration
        call_command("makemigrations", "--check", verbosity=0)
