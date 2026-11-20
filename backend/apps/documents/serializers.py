"""
Django REST Framework Serializers for Document Intelligence & Financial Validation API.
Provides validation, serialization, and deserialization for documents, extractions,
validation findings, audit history, and cross-document reconciliation.
"""
from decimal import Decimal
import os
from typing import Any, Dict, List, Optional
import uuid

from django.conf import settings
from rest_framework import serializers

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


class LineItemSerializer(serializers.ModelSerializer):
    """Serializes line items extracted from invoices."""

    class Meta:
        model = LineItem
        fields = [
            "id",
            "line_number",
            "description",
            "quantity",
            "unit_price",
            "amount",
        ]
        read_only_fields = fields


class ValidationErrorSerializer(serializers.ModelSerializer):
    """Serializes deterministic financial validation findings and anomalies."""

    class Meta:
        model = ValidationError
        fields = [
            "id",
            "rule_id",
            "field",
            "message",
            "severity",
            "actual_value",
            "expected_value",
            "difference",
            "is_dismissed",
            "dismissed_by",
            "dismissed_at",
        ]
        read_only_fields = fields


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializes immutable audit history entries for document lifecycle events."""

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "action",
            "user_id",
            "field_name",
            "old_value",
            "new_value",
            "reason",
            "created_at",
        ]
        read_only_fields = fields


class InvoiceExtractionSerializer(serializers.ModelSerializer):
    """Serializes structured financial extraction results with itemized line items."""
    line_items = LineItemSerializer(many=True, read_only=True)

    class Meta:
        model = InvoiceExtraction
        fields = [
            "id",
            "invoice_number",
            "invoice_date",
            "due_date",
            "supplier_name",
            "supplier_address",
            "customer_name",
            "customer_address",
            "subtotal",
            "tax",
            "total",
            "currency",
            "raw_text_evidence",
            "confidence_score",
            "llm_model",
            "created_at",
            "updated_at",
            "line_items",
        ]
        read_only_fields = fields


class DocumentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for document listing, status, and summary display."""

    class Meta:
        model = Document
        fields = [
            "id",
            "filename",
            "file_type",
            "file_size_bytes",
            "page_count",
            "status",
            "validation_status",
            "error_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class DocumentDetailSerializer(serializers.ModelSerializer):
    """Comprehensive detail serializer including nested extraction, errors, and audit logs."""
    extraction = InvoiceExtractionSerializer(read_only=True)
    validation_errors = ValidationErrorSerializer(many=True, read_only=True)
    audit_logs = AuditLogSerializer(many=True, read_only=True)

    class Meta:
        model = Document
        fields = [
            "id",
            "filename",
            "file_type",
            "file_size_bytes",
            "page_count",
            "status",
            "validation_status",
            "error_message",
            "raw_text",
            "metadata",
            "created_at",
            "updated_at",
            "extraction",
            "validation_errors",
            "audit_logs",
        ]
        read_only_fields = fields


class DocumentStatusSerializer(serializers.ModelSerializer):
    """Lightweight polling serializer for tracking document ingestion and validation progress."""

    class Meta:
        model = Document
        fields = [
            "id",
            "status",
            "validation_status",
            "error_message",
            "updated_at",
        ]
        read_only_fields = fields


class DocumentUploadSerializer(serializers.Serializer):
    """
    Validates server-side document upload requests.
    Enforces allowed extensions, maximum file size limits, and non-empty file contents.
    Supports raw_text directly or file upload.
    """
    file = serializers.FileField(required=False, allow_null=True)
    raw_text = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        uploaded_file = attrs.get("file")
        raw_text = attrs.get("raw_text")

        if not uploaded_file and not raw_text:
            raise serializers.ValidationError(
                {"file": "Must provide either an uploaded file or raw_text content."}
            )

        if uploaded_file:
            # 1. File size validation
            max_size = getattr(settings, "MAX_UPLOAD_SIZE_BYTES", 25 * 1024 * 1024)
            if uploaded_file.size > max_size:
                max_mb = max_size / (1024 * 1024)
                raise serializers.ValidationError(
                    {"file": f"File size exceeds maximum allowed limit of {max_mb:.0f} MB."}
                )

            if uploaded_file.size == 0:
                raise serializers.ValidationError(
                    {"file": "Uploaded file is empty (0 bytes)."}
                )

            # 2. File extension validation
            original_filename = os.path.basename(uploaded_file.name or "")
            ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""
            allowed_exts = getattr(
                settings,
                "ALLOWED_DOCUMENT_EXTENSIONS",
                {"pdf", "png", "jpg", "jpeg", "tiff", "tif", "xlsx", "xls", "csv", "txt"},
            )

            if ext not in allowed_exts:
                allowed_str = ", ".join(sorted(allowed_exts))
                raise serializers.ValidationError(
                    {"file": f"Unsupported file extension '.{ext}'. Allowed types: {allowed_str}."}
                )

            attrs["cleaned_filename"] = original_filename
            attrs["cleaned_extension"] = ext
            attrs["cleaned_size"] = uploaded_file.size

        return attrs


class DocumentReprocessSerializer(serializers.Serializer):
    """Validates document reprocessing/retry requests."""
    force = serializers.BooleanField(
        default=False,
        help_text="If True, forces reprocessing of documents previously in SUCCESS or FAILED state.",
    )


class CrossReconciliationRequestSerializer(serializers.Serializer):
    """
    Validates cross-document verification requests.
    Requires two distinct documents that both have structured extraction records.
    """
    doc_a_id = serializers.UUIDField(required=True)
    doc_b_id = serializers.UUIDField(required=True)
    tolerance = serializers.DecimalField(
        max_digits=5,
        decimal_places=4,
        required=False,
        default=Decimal("0.05"),
        help_text="Arithmetic discrepancy tolerance threshold (default: 0.05).",
    )

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        doc_a_id = attrs["doc_a_id"]
        doc_b_id = attrs["doc_b_id"]

        if doc_a_id == doc_b_id:
            raise serializers.ValidationError(
                "Self-reconciliation is not permitted. 'doc_a_id' and 'doc_b_id' must be distinct documents."
            )

        doc_a = Document.objects.filter(id=doc_a_id).first()
        if not doc_a:
            raise serializers.ValidationError({"doc_a_id": f"Document A ({doc_a_id}) not found."})

        doc_b = Document.objects.filter(id=doc_b_id).first()
        if not doc_b:
            raise serializers.ValidationError({"doc_b_id": f"Document B ({doc_b_id}) not found."})

        ext_a = getattr(doc_a, "extraction", None)
        if not ext_a:
            raise serializers.ValidationError(
                {"doc_a_id": f"Document A ({doc_a.filename}) has not completed extraction or has no structured extraction record."}
            )

        ext_b = getattr(doc_b, "extraction", None)
        if not ext_b:
            raise serializers.ValidationError(
                {"doc_b_id": f"Document B ({doc_b.filename}) has not completed extraction or has no structured extraction record."}
            )

        attrs["doc_a"] = doc_a
        attrs["doc_b"] = doc_b
        return attrs


class LineItemCorrectionSerializer(serializers.Serializer):
    """Input serializer for line item manual creation or editing."""
    id = serializers.UUIDField(required=False, allow_null=True)
    line_number = serializers.IntegerField(required=False, min_value=1)
    description = serializers.CharField(required=True, allow_blank=False)
    quantity = serializers.DecimalField(max_digits=14, decimal_places=4, required=False, allow_null=True)
    unit_price = serializers.DecimalField(max_digits=14, decimal_places=4, required=False, allow_null=True)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, allow_null=True)


class DocumentCorrectionSerializer(serializers.Serializer):
    """Input serializer for manual operator correction of invoice headers and line items."""
    invoice_number = serializers.CharField(max_length=128, required=False, allow_null=True, allow_blank=True)
    invoice_date = serializers.DateField(required=False, allow_null=True)
    due_date = serializers.DateField(required=False, allow_null=True)
    supplier_name = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    supplier_address = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    customer_name = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    customer_address = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, allow_null=True)
    tax = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, allow_null=True)
    total = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, allow_null=True)
    currency = serializers.CharField(max_length=16, required=False, allow_null=True, allow_blank=True)
    line_items = LineItemCorrectionSerializer(many=True, required=False)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="Manual operator correction")
    operator = serializers.CharField(max_length=128, required=False, allow_blank=True, allow_null=True, default=None)

    def validate_currency(self, value):
        if value is not None:
            cleaned = value.strip().upper()
            if len(cleaned) > 16:
                raise serializers.ValidationError("Currency code or symbol cannot exceed 16 characters.")
            return cleaned
        return value


class CrossReconciliationSerializer(serializers.ModelSerializer):
    """Serializes paired document reconciliation findings, match counts, and status."""
    doc_a_details = serializers.SerializerMethodField()
    doc_b_details = serializers.SerializerMethodField()
    comparison_matrix = serializers.SerializerMethodField()

    class Meta:
        model = CrossReconciliation
        fields = [
            "id",
            "doc_a",
            "doc_b",
            "doc_a_details",
            "doc_b_details",
            "comparison_matrix",
            "status",
            "is_reconciled",
            "discrepancies",
            "warnings",
            "fields_compared",
            "matched_items_count",
            "unmatched_items_count",
            "summary",
            "created_at",
        ]
        read_only_fields = fields

    def get_doc_a_details(self, obj):
        if not obj.doc_a:
            return None
        return self._format_doc_summary(obj.doc_a)

    def get_doc_b_details(self, obj):
        if not obj.doc_b:
            return None
        return self._format_doc_summary(obj.doc_b)

    def _format_doc_summary(self, doc):
        ext = getattr(doc, "extraction", None)
        ext_data = None
        if ext:
            ext_data = {
                "id": str(ext.id),
                "invoice_number": ext.invoice_number,
                "invoice_date": str(ext.invoice_date) if ext.invoice_date else None,
                "due_date": str(ext.due_date) if ext.due_date else None,
                "supplier_name": ext.supplier_name,
                "supplier_address": ext.supplier_address,
                "customer_name": ext.customer_name,
                "customer_address": ext.customer_address,
                "subtotal": str(ext.subtotal) if ext.subtotal is not None else None,
                "tax": str(ext.tax) if ext.tax is not None else None,
                "total": str(ext.total) if ext.total is not None else None,
                "currency": ext.currency,
                "confidence_score": ext.confidence_score,
                "line_items": [
                    {
                        "id": str(li.id),
                        "line_number": li.line_number,
                        "description": li.description,
                        "quantity": str(li.quantity) if li.quantity is not None else None,
                        "unit_price": str(li.unit_price) if li.unit_price is not None else None,
                        "amount": str(li.amount) if li.amount is not None else None,
                    }
                    for li in ext.line_items.all().order_by("line_number")
                ],
            }
        return {
            "id": str(doc.id),
            "filename": doc.filename,
            "file_type": doc.file_type,
            "file_size_bytes": doc.file_size_bytes,
            "status": doc.status,
            "validation_status": doc.validation_status,
            "metadata": doc.metadata or {},
            "extraction": ext_data,
        }

    def get_comparison_matrix(self, obj):
        """Builds structured comparison matrix rows across standard header fields."""
        if not obj.doc_a or not obj.doc_b:
            return []

        ext_a = getattr(obj.doc_a, "extraction", None)
        ext_b = getattr(obj.doc_b, "extraction", None)
        if not ext_a or not ext_b:
            return []

        meta_a = (obj.doc_a.metadata or {}).get("manual_corrections") or {}
        meta_b = (obj.doc_b.metadata or {}).get("manual_corrections") or {}
        orig_a = meta_a.get("original_extraction") or {}
        orig_b = meta_b.get("original_extraction") or {}
        corr_fields_a = set(meta_a.get("corrected_fields") or [])
        corr_fields_b = set(meta_b.get("corrected_fields") or [])

        discrepancies_by_field = {d.get("field"): d for d in (obj.discrepancies or [])}
        warnings_by_field = {w.get("field"): w for w in (obj.warnings or [])}

        fields_to_compare = [
            ("invoice_number", "Invoice / Ref Number"),
            ("invoice_date", "Invoice Date"),
            ("supplier_name", "Supplier / Vendor"),
            ("customer_name", "Customer / Bill-To"),
            ("currency", "Currency"),
            ("subtotal", "Subtotal"),
            ("tax", "Tax / VAT"),
            ("total", "Total Amount"),
        ]

        matrix = []
        for field_key, label in fields_to_compare:
            val_a = getattr(ext_a, field_key, None)
            val_b = getattr(ext_b, field_key, None)
            val_a_str = str(val_a) if val_a is not None else None
            val_b_str = str(val_b) if val_b is not None else None

            disc = discrepancies_by_field.get(field_key)
            warn = warnings_by_field.get(field_key)

            if disc:
                match_status = "DISCREPANCY"
                diff = disc.get("difference")
                message = disc.get("message")
            elif warn:
                match_status = "WARNING"
                diff = warn.get("difference")
                message = warn.get("message")
            elif val_a_str is None or val_b_str is None:
                match_status = "MISSING"
                diff = None
                message = "Value missing in one or both documents"
            else:
                match_status = "MATCH"
                diff = None
                message = "Values match within tolerance"

            matrix.append({
                "field": field_key,
                "label": label,
                "doc_a_value": val_a_str,
                "doc_b_value": val_b_str,
                "doc_a_is_corrected": field_key in corr_fields_a,
                "doc_b_is_corrected": field_key in corr_fields_b,
                "doc_a_original": str(orig_a.get(field_key)) if field_key in orig_a else None,
                "doc_b_original": str(orig_b.get(field_key)) if field_key in orig_b else None,
                "status": match_status,
                "difference": str(diff) if diff is not None else None,
                "message": message,
            })

        return matrix

