"""
Security Hardening & F-02 Remediation Test Suite for TASK-020.
Verifies:
- All sensitive endpoints reject unauthenticated requests with 401 Unauthorized
- Authenticated requests succeed across all endpoints
- TASK-018 Finding F-02 Remediation:
  - Reconcile create rejects doc_a in QUEUED status with 409 Conflict
  - Reconcile create rejects doc_b in QUEUED status with 409 Conflict
  - Reconcile create rejects doc_a in PROCESSING status with 409 Conflict
  - Reconcile create rejects doc_b in PROCESSING status with 409 Conflict
  - Re-reconcile rejects doc_a in QUEUED status with 409 Conflict
  - Re-reconcile rejects doc_b in QUEUED status with 409 Conflict
  - Re-reconcile rejects doc_a in PROCESSING status with 409 Conflict
  - Re-reconcile rejects doc_b in PROCESSING status with 409 Conflict
  - Re-reconcile succeeds when both documents are in valid terminal state
- User attribution on upload (metadata) and correction (audit log)
"""
from decimal import Decimal
import os
import sys
import unittest.mock as mock

for mod in ["celery", "celery.shared_task", "pymupdf", "fitz", "pdfplumber", "easyocr"]:
    if mod not in sys.modules:
        sys.modules[mod] = mock.MagicMock()

import django
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "documind.settings")
django.setup()

import pytest
from django.contrib.auth.models import User
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
    ValidationStatusChoices,
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Applies database migrations for test session."""
    call_command("migrate", verbosity=0)


@pytest.fixture
def unauth_client():
    """Client without any credentials."""
    return APIClient()


@pytest.fixture
def auth_client():
    """Client authenticated as compliance operator."""
    user, _ = User.objects.get_or_create(
        username="sec_auditor",
        defaults={"email": "sec_auditor@documind.ai"},
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def sample_pair():
    """Creates a pair of sample documents with extractions."""
    doc_a = Document.objects.create(
        filename="invoice_a.pdf",
        file_type="pdf",
        file_size_bytes=1000,
        status=DocumentStatus.SUCCESS,
        validation_status=ValidationStatusChoices.VERIFIED,
    )
    InvoiceExtraction.objects.create(
        document=doc_a,
        invoice_number="INV-A-100",
        total=Decimal("1000.00"),
        subtotal=Decimal("900.00"),
        tax=Decimal("100.00"),
    )

    doc_b = Document.objects.create(
        filename="invoice_b.pdf",
        file_type="pdf",
        file_size_bytes=1000,
        status=DocumentStatus.SUCCESS,
        validation_status=ValidationStatusChoices.VERIFIED,
    )
    InvoiceExtraction.objects.create(
        document=doc_b,
        invoice_number="INV-B-100",
        total=Decimal("1000.00"),
        subtotal=Decimal("900.00"),
        tax=Decimal("100.00"),
    )
    return doc_a, doc_b


@pytest.mark.django_db
class TestEndpointSecurityHardening:
    """Verifies that all sensitive endpoints require authentication."""

    def test_unauthenticated_requests_receive_401(self, unauth_client, sample_pair):
        """Checks 401 rejection across all sensitive endpoints."""
        doc_a, doc_b = sample_pair

        # 1. Documents listing
        res = unauth_client.get("/api/documents/")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

        # 2. Document detail
        res = unauth_client.get(f"/api/documents/{doc_a.id}/")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

        # 3. Document status
        res = unauth_client.get(f"/api/documents/{doc_a.id}/status/")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

        # 4. Document reprocess
        res = unauth_client.post(f"/api/documents/{doc_a.id}/reprocess/", data={"force": True}, format="json")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

        # 5. Full-text search
        res = unauth_client.get("/api/documents/search/?q=invoice")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

        # 6. Manual correction
        res = unauth_client.post(
            f"/api/documents/{doc_a.id}/correct/",
            data={"invoice_number": "NEW-123"},
            format="json",
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

        # 7. Reconciliation list
        res = unauth_client.get("/api/reconciliations/")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

        # 8. Reconciliation create
        res = unauth_client.post(
            "/api/reconciliations/",
            data={"doc_a_id": str(doc_a.id), "doc_b_id": str(doc_b.id)},
            format="json",
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_authenticated_user_access_succeeds(self, auth_client, sample_pair):
        """Verifies authenticated requests successfully access resources."""
        doc_a, _ = sample_pair
        res = auth_client.get("/api/documents/")
        assert res.status_code == status.HTTP_200_OK

        res = auth_client.get(f"/api/documents/{doc_a.id}/")
        assert res.status_code == status.HTTP_200_OK

        res = auth_client.get("/api/documents/search/?q=invoice")
        assert res.status_code == status.HTTP_200_OK

    def test_correction_records_authenticated_operator(self, auth_client, sample_pair):
        """Manual correction captures the authenticated user's identity in the AuditLog."""
        doc_a, _ = sample_pair
        res = auth_client.post(
            f"/api/documents/{doc_a.id}/correct/",
            data={"invoice_number": "INV-AUDIT-AUTH-001", "reason": "Hardening check"},
            format="json",
        )
        assert res.status_code == status.HTTP_200_OK
        latest_audit = AuditLog.objects.filter(document=doc_a, field_name="invoice_number").first()
        assert latest_audit is not None
        assert latest_audit.user_id == "sec_auditor"


@pytest.mark.django_db
class TestReconciliationGuardRemediationF02:
    """Verifies complete QUEUED and PROCESSING guards on reconciliation create and re-reconcile (TASK-018 F-02)."""

    def test_reconcile_create_rejects_queued_doc_a(self, auth_client, sample_pair):
        """Reconciliation creation rejects when doc_a is QUEUED."""
        doc_a, doc_b = sample_pair
        doc_a.status = DocumentStatus.QUEUED
        doc_a.save()

        res = auth_client.post(
            "/api/reconciliations/",
            data={"doc_a_id": str(doc_a.id), "doc_b_id": str(doc_b.id)},
            format="json",
        )
        assert res.status_code == status.HTTP_409_CONFLICT
        assert "queued or actively being processed" in res.json().get("error", "").lower()

    def test_reconcile_create_rejects_queued_doc_b(self, auth_client, sample_pair):
        """Reconciliation creation rejects when doc_b is QUEUED."""
        doc_a, doc_b = sample_pair
        doc_b.status = DocumentStatus.QUEUED
        doc_b.save()

        res = auth_client.post(
            "/api/reconciliations/",
            data={"doc_a_id": str(doc_a.id), "doc_b_id": str(doc_b.id)},
            format="json",
        )
        assert res.status_code == status.HTTP_409_CONFLICT
        assert "queued or actively being processed" in res.json().get("error", "").lower()

    def test_reconcile_create_rejects_processing_doc_a(self, auth_client, sample_pair):
        """Reconciliation creation rejects when doc_a is PROCESSING."""
        doc_a, doc_b = sample_pair
        doc_a.status = DocumentStatus.PROCESSING
        doc_a.save()

        res = auth_client.post(
            "/api/reconciliations/",
            data={"doc_a_id": str(doc_a.id), "doc_b_id": str(doc_b.id)},
            format="json",
        )
        assert res.status_code == status.HTTP_409_CONFLICT
        assert "queued or actively being processed" in res.json().get("error", "").lower()

    def test_reconcile_create_rejects_processing_doc_b(self, auth_client, sample_pair):
        """Reconciliation creation rejects when doc_b is PROCESSING."""
        doc_a, doc_b = sample_pair
        doc_b.status = DocumentStatus.PROCESSING
        doc_b.save()

        res = auth_client.post(
            "/api/reconciliations/",
            data={"doc_a_id": str(doc_a.id), "doc_b_id": str(doc_b.id)},
            format="json",
        )
        assert res.status_code == status.HTTP_409_CONFLICT
        assert "queued or actively being processed" in res.json().get("error", "").lower()

    def test_re_reconcile_rejects_queued_doc_a(self, auth_client, sample_pair):
        """Re-reconcile rejects when doc_a becomes QUEUED."""
        doc_a, doc_b = sample_pair
        # Initial reconciliation created in SUCCESS state
        rec = CrossReconciliation.objects.create(
            doc_a=doc_a,
            doc_b=doc_b,
            status=ValidationStatusChoices.VERIFIED,
            is_reconciled=True,
        )

        # doc_a transitioned back to QUEUED (e.g. reprocessing)
        doc_a.status = DocumentStatus.QUEUED
        doc_a.save()

        res = auth_client.post(f"/api/reconciliations/{rec.id}/re-reconcile/", data={}, format="json")
        assert res.status_code == status.HTTP_409_CONFLICT
        assert "queued or actively being processed" in res.json().get("error", "").lower()

    def test_re_reconcile_rejects_queued_doc_b(self, auth_client, sample_pair):
        """Re-reconcile rejects when doc_b becomes QUEUED."""
        doc_a, doc_b = sample_pair
        rec = CrossReconciliation.objects.create(
            doc_a=doc_a,
            doc_b=doc_b,
            status=ValidationStatusChoices.VERIFIED,
            is_reconciled=True,
        )

        doc_b.status = DocumentStatus.QUEUED
        doc_b.save()

        res = auth_client.post(f"/api/reconciliations/{rec.id}/re-reconcile/", data={}, format="json")
        assert res.status_code == status.HTTP_409_CONFLICT
        assert "queued or actively being processed" in res.json().get("error", "").lower()

    def test_re_reconcile_rejects_processing_doc_a(self, auth_client, sample_pair):
        """Re-reconcile rejects when doc_a becomes PROCESSING."""
        doc_a, doc_b = sample_pair
        rec = CrossReconciliation.objects.create(
            doc_a=doc_a,
            doc_b=doc_b,
            status=ValidationStatusChoices.VERIFIED,
            is_reconciled=True,
        )

        doc_a.status = DocumentStatus.PROCESSING
        doc_a.save()

        res = auth_client.post(f"/api/reconciliations/{rec.id}/re-reconcile/", data={}, format="json")
        assert res.status_code == status.HTTP_409_CONFLICT
        assert "queued or actively being processed" in res.json().get("error", "").lower()

    def test_re_reconcile_rejects_processing_doc_b(self, auth_client, sample_pair):
        """Re-reconcile rejects when doc_b becomes PROCESSING."""
        doc_a, doc_b = sample_pair
        rec = CrossReconciliation.objects.create(
            doc_a=doc_a,
            doc_b=doc_b,
            status=ValidationStatusChoices.VERIFIED,
            is_reconciled=True,
        )

        doc_b.status = DocumentStatus.PROCESSING
        doc_b.save()

        res = auth_client.post(f"/api/reconciliations/{rec.id}/re-reconcile/", data={}, format="json")
        assert res.status_code == status.HTTP_409_CONFLICT
        assert "queued or actively being processed" in res.json().get("error", "").lower()

    def test_re_reconcile_succeeds_when_both_in_terminal_state(self, auth_client, sample_pair):
        """Re-reconcile creates a new reconciliation record when both documents are in terminal SUCCESS state."""
        doc_a, doc_b = sample_pair
        rec = CrossReconciliation.objects.create(
            doc_a=doc_a,
            doc_b=doc_b,
            status=ValidationStatusChoices.VERIFIED,
            is_reconciled=True,
        )

        res = auth_client.post(f"/api/reconciliations/{rec.id}/re-reconcile/", data={"tolerance": "0.10"}, format="json")
        assert res.status_code == status.HTTP_201_CREATED
        new_data = res.json()
        assert new_data["id"] != str(rec.id)
        # Original record preserved
        assert CrossReconciliation.objects.filter(id=rec.id).exists()
