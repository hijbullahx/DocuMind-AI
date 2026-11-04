"""
Django Database Models for DocuMind-AI Document Persistence.
Implements relational storage for uploaded documents, structured invoice extractions,
line items, validation errors, audit history, and cross-document reconciliation records.
"""
from decimal import Decimal
import uuid
from typing import Any, Dict, List, Optional

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from django.utils import timezone


class DocumentStatus(models.TextChoices):
    """Lifecycle status for document ingestion and processing."""
    QUEUED = 'QUEUED', 'Queued'
    PROCESSING = 'PROCESSING', 'Processing'
    SUCCESS = 'SUCCESS', 'Success'
    PARTIAL_SUCCESS = 'PARTIAL_SUCCESS', 'Partial Success'
    FAILED = 'FAILED', 'Failed'


class ValidationStatusChoices(models.TextChoices):
    """Status outcomes from deterministic financial validation and cross-reconciliation."""
    PENDING = 'PENDING', 'Pending'
    VERIFIED = 'VERIFIED', 'Verified'
    NEEDS_REVIEW = 'NEEDS_REVIEW', 'Needs Review'
    FAILED = 'FAILED', 'Failed'


class ValidationSeverityChoices(models.TextChoices):
    """Severity ratings for discrepancy and validation rule findings."""
    ERROR = 'ERROR', 'Error'
    WARNING = 'WARNING', 'Warning'
    INFO = 'INFO', 'Info'


class Document(models.Model):
    """
    Source document uploaded to the system.
    Represents the file container, ingestion metadata, text content, and pipeline status.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to='documents/%Y/%m/%d/', blank=True, null=True)
    filename = models.CharField(max_length=255, db_index=True)
    file_type = models.CharField(max_length=32, db_index=True)  # pdf, png, jpg, tiff, xlsx, xls, csv
    file_size_bytes = models.BigIntegerField(default=0)
    page_count = models.IntegerField(default=1)

    status = models.CharField(
        max_length=32,
        choices=DocumentStatus.choices,
        default=DocumentStatus.QUEUED,
        db_index=True,
    )
    validation_status = models.CharField(
        max_length=32,
        choices=ValidationStatusChoices.choices,
        default=ValidationStatusChoices.PENDING,
        db_index=True,
    )

    error_message = models.TextField(blank=True, null=True)
    raw_text = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['validation_status']),
            models.Index(fields=['filename']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self) -> str:
        return f"{self.filename} ({self.id}) - {self.status}"

    def clean(self) -> None:
        super().clean()
        if self.status and self.status not in DocumentStatus.values:
            raise DjangoValidationError({"status": f"Invalid document status: {self.status}"})
        if self.validation_status and self.validation_status not in ValidationStatusChoices.values:
            raise DjangoValidationError({"validation_status": f"Invalid validation status: {self.validation_status}"})

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class InvoiceExtraction(models.Model):
    """
    Structured financial extraction record derived from a source Document.
    1:1 relationship with Document.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        related_name='extraction',
    )
    invoice_number = models.CharField(max_length=128, blank=True, null=True, db_index=True)
    invoice_date = models.DateField(blank=True, null=True, db_index=True)
    due_date = models.DateField(blank=True, null=True)
    supplier_name = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    supplier_address = models.TextField(blank=True, null=True)
    customer_name = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    customer_address = models.TextField(blank=True, null=True)

    subtotal = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    tax = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    total = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True, db_index=True)
    currency = models.CharField(max_length=16, blank=True, null=True)

    raw_text_evidence = models.JSONField(default=dict, blank=True)
    confidence_score = models.FloatField(blank=True, null=True)
    llm_model = models.CharField(max_length=64, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['supplier_name', 'invoice_number']),
            models.Index(fields=['invoice_date']),
            models.Index(fields=['total']),
        ]

    def __str__(self) -> str:
        return f"Extraction for {self.document.filename}: {self.invoice_number or 'N/A'} ({self.total} {self.currency or ''})"


class LineItem(models.Model):
    """
    Itemized product or service record associated with an InvoiceExtraction.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    extraction = models.ForeignKey(
        InvoiceExtraction,
        on_delete=models.CASCADE,
        related_name='line_items',
    )
    line_number = models.IntegerField(default=1)
    description = models.TextField()
    quantity = models.DecimalField(max_digits=14, decimal_places=4, blank=True, null=True)
    unit_price = models.DecimalField(max_digits=14, decimal_places=4, blank=True, null=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['extraction', 'line_number', 'id']
        indexes = [
            models.Index(fields=['extraction', 'line_number']),
        ]

    def __str__(self) -> str:
        return f"Line {self.line_number}: {self.description[:30]} ({self.amount})"


class ValidationError(models.Model):
    """
    Mathematical discrepancy, anomaly, or review finding identified on a Document.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='validation_errors',
    )
    rule_id = models.CharField(max_length=64, db_index=True)
    field = models.CharField(max_length=128)
    message = models.TextField()
    severity = models.CharField(
        max_length=16,
        choices=ValidationSeverityChoices.choices,
        default=ValidationSeverityChoices.ERROR,
    )
    actual_value = models.TextField(blank=True, null=True)
    expected_value = models.TextField(blank=True, null=True)
    difference = models.DecimalField(max_digits=14, decimal_places=4, blank=True, null=True)

    is_dismissed = models.BooleanField(default=False)
    dismissed_by = models.CharField(max_length=128, blank=True, null=True)
    dismissed_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['severity', 'created_at']
        indexes = [
            models.Index(fields=['document', 'severity']),
            models.Index(fields=['rule_id']),
        ]

    def __str__(self) -> str:
        return f"[{self.severity}] {self.rule_id} on {self.document.filename} ({self.field})"

    def dismiss(self, operator: str) -> None:
        """Marks the validation finding as dismissed by an operator during manual review."""
        self.is_dismissed = True
        self.dismissed_by = operator
        self.dismissed_at = timezone.now()
        self.save(update_fields=['is_dismissed', 'dismissed_by', 'dismissed_at'])


class AuditLog(models.Model):
    """
    Immutable audit trail recording manual operator edits, field overrides, and review decisions.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='audit_logs',
    )
    user_id = models.CharField(max_length=128, default='system')
    action = models.CharField(max_length=64, db_index=True)  # MANUAL_CORRECTION, DISMISS_WARNING, STATUS_CHANGE, REPROCESS
    field_name = models.CharField(max_length=128, blank=True, null=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    reason = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['document', 'created_at']),
            models.Index(fields=['action']),
        ]

    def __str__(self) -> str:
        return f"{self.action} on {self.document.filename} by {self.user_id} at {self.created_at}"

    def save(self, *args, **kwargs) -> None:
        """Enforces model-level immutability: existing records cannot be modified."""
        if self.pk and not self._state.adding:
            raise PermissionError("AuditLog entries are immutable and cannot be modified once created.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs) -> None:
        """Enforces model-level immutability: records cannot be deleted directly."""
        raise PermissionError("AuditLog entries are immutable and cannot be deleted directly.")


class CrossReconciliation(models.Model):
    """
    Outcome of two-document cross-verification (e.g. PDF Invoice vs PO, or PDF vs Excel ledger).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    doc_a = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='reconciliations_as_a',
    )
    doc_b = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='reconciliations_as_b',
    )
    status = models.CharField(
        max_length=32,
        choices=ValidationStatusChoices.choices,
        default=ValidationStatusChoices.PENDING,
        db_index=True,
    )
    is_reconciled = models.BooleanField(default=False)
    discrepancies = models.JSONField(default=list, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    fields_compared = models.JSONField(default=list, blank=True)
    matched_items_count = models.IntegerField(default=0)
    unmatched_items_count = models.IntegerField(default=0)
    summary = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['doc_a', 'doc_b']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(doc_a=models.F('doc_b')),
                name='prevent_self_reconciliation',
            ),
        ]

    def __str__(self) -> str:
        return f"Reconciliation ({self.doc_a.filename} vs {self.doc_b.filename}): {self.status}"

    def clean(self) -> None:
        super().clean()
        if self.doc_a_id and self.doc_b_id and self.doc_a_id == self.doc_b_id:
            raise DjangoValidationError({"doc_b": "Cross-reconciliation requires two distinct documents; self-reconciliation is not permitted."})

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)
