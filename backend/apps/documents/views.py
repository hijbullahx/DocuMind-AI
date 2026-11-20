"""
Django REST Framework Views and ViewSets for Document Intelligence API.
Exposes REST endpoints for document ingestion, detail inspection, status polling,
failure retry/reprocessing, and cross-document reconciliation.
"""
from decimal import Decimal
import logging
import os
from typing import Any, Dict, List, Optional
import uuid

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Q
from django.http import Http404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.documents.models import (
    AuditLog,
    CrossReconciliation,
    Document,
    DocumentStatus,
    InvoiceExtraction,
    LineItem,
    ValidationError,
    ValidationStatusChoices,
)
from apps.documents.search import apply_document_search
from apps.documents.serializers import (
    CrossReconciliationRequestSerializer,
    CrossReconciliationSerializer,
    DocumentCorrectionSerializer,
    DocumentDetailSerializer,
    DocumentListSerializer,
    DocumentReprocessSerializer,
    DocumentStatusSerializer,
    DocumentUploadSerializer,
)
from apps.documents.tasks import (
    process_document_task,
    reconcile_documents_task,
)

logger = logging.getLogger(__name__)


class DocumentPagination(PageNumberPagination):
    """Configurable page-number pagination for document lists."""
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class DocumentViewSet(viewsets.ModelViewSet):
    """
    REST ViewSet managing the complete document lifecycle.
    - list (GET /api/documents/): Paginated listing with filtering and search.
    - retrieve (GET /api/documents/{id}/): Comprehensive detail view with extractions and errors.
    - create (POST /api/documents/): Upload file or raw text, enqueue async processing.
    - status (GET /api/documents/{id}/status/): Lightweight status polling endpoint.
    - reprocess (POST /api/documents/{id}/reprocess/): Safe retry or forced re-processing.
    """
    permission_classes = [AllowAny]
    pagination_class = DocumentPagination
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        """Returns optimized queryset with related extractions and validation errors."""
        qs = Document.objects.all().select_related("extraction").prefetch_related(
            "extraction__line_items",
            "validation_errors",
            "audit_logs",
        )

        # 1. Filter by status
        doc_status = self.request.query_params.get("status")
        if doc_status:
            status_upper = doc_status.strip().upper()
            if status_upper in DocumentStatus.values:
                qs = qs.filter(status=status_upper)

        # 2. Filter by validation_status
        val_status = self.request.query_params.get("validation_status")
        if val_status:
            val_upper = val_status.strip().upper()
            if val_upper in ValidationStatusChoices.values:
                qs = qs.filter(validation_status=val_upper)

        # 3. Filter by file_type
        file_type = self.request.query_params.get("file_type")
        if file_type:
            qs = qs.filter(file_type__iexact=file_type.strip())

        # 4. Search query (PostgreSQL FTS or robust multi-field fallback)
        search_query = self.request.query_params.get("search")
        ordering_param = self.request.query_params.get("ordering")
        allowed_ordering = {
            "created_at", "-created_at",
            "filename", "-filename",
            "status", "-status",
            "file_size_bytes", "-file_size_bytes",
        }
        chosen_ordering = ordering_param if ordering_param in allowed_ordering else None

        if search_query:
            qs = apply_document_search(qs, search_query, user_ordering=chosen_ordering)

        # 5. Ordering
        if chosen_ordering:
            qs = qs.order_by(chosen_ordering)
        elif not search_query or connection.vendor != "postgresql":
            # In PostgreSQL search with default ordering, apply_postgres_fts orders by -search_rank
            qs = qs.order_by("-created_at")

        return qs

    def get_serializer_class(self):
        """Dynamic serializer selection based on action."""
        if self.action == "list":
            return DocumentListSerializer
        elif self.action == "retrieve":
            return DocumentDetailSerializer
        elif self.action == "create":
            return DocumentUploadSerializer
        elif self.action == "status":
            return DocumentStatusSerializer
        elif self.action == "reprocess":
            return DocumentReprocessSerializer
        elif self.action == "correct":
            return DocumentCorrectionSerializer
        return DocumentDetailSerializer

    def get_object(self) -> Document:
        """Validates UUID primary key format and retrieves document or raises 404."""
        pk_val = self.kwargs.get("pk", "")
        try:
            uuid_obj = uuid.UUID(str(pk_val))
        except (ValueError, TypeError, AttributeError):
            raise DRFValidationError({"error": f"Invalid document ID format '{pk_val}'. Expected UUID."})

        try:
            return self.get_queryset().get(id=uuid_obj)
        except Document.DoesNotExist:
            raise Http404(f"Document with ID {pk_val} not found.")

    def create(self, request: Request, *args, **kwargs) -> Response:
        """
        Uploads and enqueues a new Document for background intelligence processing.
        Validates file integrity, extension, and size server-side.
        Creates Document record with initial QUEUED status and invokes Celery pipeline task.
        """
        serializer = DocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_file = serializer.validated_data.get("file")
        raw_text = serializer.validated_data.get("raw_text")

        if uploaded_file:
            cleaned_filename = serializer.validated_data["cleaned_filename"]
            cleaned_ext = serializer.validated_data["cleaned_extension"]
            cleaned_size = serializer.validated_data["cleaned_size"]

            doc = Document.objects.create(
                file=uploaded_file,
                filename=cleaned_filename,
                file_type=cleaned_ext,
                file_size_bytes=cleaned_size,
                raw_text=raw_text or "",
                status=DocumentStatus.QUEUED,
                validation_status=ValidationStatusChoices.PENDING,
            )
        else:
            # Direct raw text ingestion without physical file
            text_bytes = (raw_text or "").encode("utf-8")
            doc = Document.objects.create(
                filename="pasted_content.txt",
                file_type="txt",
                file_size_bytes=len(text_bytes),
                raw_text=raw_text,
                status=DocumentStatus.QUEUED,
                validation_status=ValidationStatusChoices.PENDING,
            )

        logger.info(f"[API] Created document {doc.id} ({doc.filename}). Enqueueing Celery processing task.")

        # Enqueue async background task
        process_document_task.delay(str(doc.id))

        response_data = DocumentListSerializer(doc).data
        response_data["message"] = "Document uploaded successfully and queued for processing."
        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="status")
    def status(self, request: Request, pk=None) -> Response:
        """Lightweight endpoint for polling document ingestion and validation state."""
        doc = self.get_object()
        serializer = DocumentStatusSerializer(doc)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reprocess")
    def reprocess(self, request: Request, pk=None) -> Response:
        """
        Triggers safe retry or forced reprocessing of a document.
        Respects atomic claim and duplicate guard semantics.
        """
        doc = self.get_object()
        serializer = DocumentReprocessSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        force = serializer.validated_data.get("force", False)

        # 1. Guard against competing active processing
        if doc.status == DocumentStatus.PROCESSING:
            return Response(
                {
                    "error": "Document is already being processed.",
                    "document_id": str(doc.id),
                    "status": doc.status,
                },
                status=status.HTTP_409_CONFLICT,
            )

        # 2. Guard against unnecessary rerun without force
        if doc.status in (DocumentStatus.SUCCESS, DocumentStatus.PARTIAL_SUCCESS) and not force:
            return Response(
                {
                    "error": f"Document has already been successfully processed (status: {doc.status}). Set force=true to reprocess.",
                    "document_id": str(doc.id),
                    "status": doc.status,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.info(f"[API] Reprocessing requested for doc {doc.id} (force={force}).")
        process_document_task.delay(str(doc.id), force=force)

        return Response(
            {
                "message": "Document reprocessing successfully initiated.",
                "document_id": str(doc.id),
                "status": DocumentStatus.PROCESSING if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False) else DocumentStatus.QUEUED,
                "force": force,
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request: Request) -> Response:
        """
        Dedicated full-text document and extraction search endpoint (TASK-019).
        Searches across:
        - Filename & Document Metadata (Tier A)
        - Extracted Invoice Number (Tier A)
        - Supplier & Customer Names (Tier B)
        - Line Item Descriptions & Addresses (Tier C)
        - Raw OCR Content (Tier D)
        Returns relevance-ranked results with bounded, XSS-safe highlighted snippets.
        """
        from apps.documents.search import search_documents_service

        q = request.query_params.get("q", "")
        status_filter = request.query_params.get("status")
        val_status_filter = request.query_params.get("validation_status")
        file_type_filter = request.query_params.get("file_type")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        supplier_filter = request.query_params.get("supplier")
        customer_filter = request.query_params.get("customer")

        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except (ValueError, TypeError):
            page = 1

        try:
            page_size = min(50, max(1, int(request.query_params.get("page_size", 10))))
        except (ValueError, TypeError):
            page_size = 10

        search_payload = search_documents_service(
            search_query=q,
            status_filter=status_filter,
            validation_status_filter=val_status_filter,
            file_type_filter=file_type_filter,
            date_from=date_from,
            date_to=date_to,
            supplier_filter=supplier_filter,
            customer_filter=customer_filter,
            page=page,
            page_size=page_size,
        )

        return Response(search_payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="correct")
    def correct(self, request: Request, pk=None) -> Response:
        """
        Applies validated operator manual corrections to structured invoice extraction and line items.
        Records an immutable audit trail entry for every changed field, re-evaluates validation rules,
        and atomically persists the updated document state.
        """
        doc = self.get_object()

        # 1. Guard against active processing
        if doc.status == DocumentStatus.PROCESSING:
            return Response(
                {
                    "error": "Document is currently being processed. Cannot apply manual corrections during active processing.",
                    "document_id": str(doc.id),
                    "status": doc.status,
                },
                status=status.HTTP_409_CONFLICT,
            )

        # 2. Guard against missing extraction
        extraction = getattr(doc, "extraction", None)
        if not extraction:
            return Response(
                {
                    "error": f"Document '{doc.filename}' does not have a structured extraction record. Only extracted documents can be corrected.",
                    "document_id": str(doc.id),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Validate correction payload
        serializer = DocumentCorrectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        operator = data.get("operator") or (request.user.username if request.user and request.user.is_authenticated else "operator")
        reason = data.get("reason") or "Manual operator correction"

        # 4. Atomic transactional persistence and audit recording
        with transaction.atomic():
            doc = Document.objects.select_for_update().get(id=doc.id)
            extraction = InvoiceExtraction.objects.select_for_update().get(id=doc.extraction.id)

            # Snapshot original machine extraction if not already preserved
            metadata = dict(doc.metadata or {})
            manual_corr = dict(metadata.get("manual_corrections") or {})
            if "original_extraction" not in manual_corr:
                manual_corr["original_extraction"] = {
                    "invoice_number": extraction.invoice_number,
                    "invoice_date": str(extraction.invoice_date) if extraction.invoice_date else None,
                    "due_date": str(extraction.due_date) if extraction.due_date else None,
                    "supplier_name": extraction.supplier_name,
                    "supplier_address": extraction.supplier_address,
                    "customer_name": extraction.customer_name,
                    "customer_address": extraction.customer_address,
                    "subtotal": str(extraction.subtotal) if extraction.subtotal is not None else None,
                    "tax": str(extraction.tax) if extraction.tax is not None else None,
                    "total": str(extraction.total) if extraction.total is not None else None,
                    "currency": extraction.currency,
                }

            changed_fields: List[str] = []
            header_fields = [
                "invoice_number", "invoice_date", "due_date",
                "supplier_name", "supplier_address",
                "customer_name", "customer_address",
                "subtotal", "tax", "total", "currency"
            ]

            for field in header_fields:
                if field in data:
                    old_val = getattr(extraction, field)
                    new_val = data[field]

                    is_different = False
                    if old_val != new_val:
                        if isinstance(old_val, Decimal) and new_val is not None:
                            try:
                                is_different = Decimal(str(old_val)) != Decimal(str(new_val))
                            except Exception:
                                is_different = True
                        else:
                            is_different = True

                    if is_different:
                        setattr(extraction, field, new_val)
                        AuditLog.objects.create(
                            document=doc,
                            user_id=operator,
                            action="MANUAL_CORRECTION",
                            field_name=field,
                            old_value=str(old_val) if old_val is not None else None,
                            new_value=str(new_val) if new_val is not None else None,
                            reason=reason,
                        )
                        changed_fields.append(field)

            # Process line items if provided in payload
            if "line_items" in data:
                old_items = list(extraction.line_items.all().order_by("line_number"))
                new_items_data = data["line_items"]

                line_items_changed = False
                if len(old_items) != len(new_items_data):
                    line_items_changed = True
                else:
                    for old_it, new_it in zip(old_items, new_items_data):
                        old_qty = old_it.quantity
                        new_qty = new_it.get("quantity")
                        old_price = old_it.unit_price
                        new_price = new_it.get("unit_price")
                        old_amt = old_it.amount
                        new_amt = new_it.get("amount")

                        if (
                            old_it.description != new_it["description"]
                            or old_qty != new_qty
                            or old_price != new_price
                            or old_amt != new_amt
                        ):
                            line_items_changed = True
                            break

                if line_items_changed:
                    old_sum = sum((it.amount or Decimal("0.00")) for it in old_items)
                    new_sum = sum((it.get("amount") or Decimal("0.00")) for it in new_items_data)
                    old_summary = f"{len(old_items)} line items (total: {old_sum})"
                    new_summary = f"{len(new_items_data)} line items (total: {new_sum})"

                    AuditLog.objects.create(
                        document=doc,
                        user_id=operator,
                        action="MANUAL_CORRECTION",
                        field_name="line_items",
                        old_value=old_summary,
                        new_value=new_summary,
                        reason=reason,
                    )

                    extraction.line_items.all().delete()
                    for idx, item_data in enumerate(new_items_data, start=1):
                        LineItem.objects.create(
                            extraction=extraction,
                            line_number=idx,
                            description=item_data["description"],
                            quantity=item_data.get("quantity"),
                            unit_price=item_data.get("unit_price"),
                            amount=item_data.get("amount"),
                        )
                    changed_fields.append("line_items")

            # Update Document metadata with correction tracking
            if changed_fields:
                manual_corr["is_corrected"] = True
                manual_corr["last_corrected_at"] = timezone.now().isoformat()
                manual_corr["last_corrected_by"] = operator
                existing_corrected = set(manual_corr.get("corrected_fields") or [])
                manual_corr["corrected_fields"] = sorted(list(existing_corrected.union(changed_fields)))
                metadata["manual_corrections"] = manual_corr
                doc.metadata = metadata
                doc.save(update_fields=["metadata", "updated_at"])
                extraction.save()

            # 5. Re-evaluate deterministic validation rules
            try:
                from apps.validation.engine import ValidationEngine
                val_engine = ValidationEngine()
                val_payload = {
                    "invoice_number": extraction.invoice_number,
                    "invoice_date": str(extraction.invoice_date) if extraction.invoice_date else None,
                    "due_date": str(extraction.due_date) if extraction.due_date else None,
                    "supplier_name": extraction.supplier_name,
                    "supplier_address": extraction.supplier_address,
                    "customer_name": extraction.customer_name,
                    "customer_address": extraction.customer_address,
                    "subtotal": extraction.subtotal,
                    "tax": extraction.tax,
                    "total": extraction.total,
                    "currency": extraction.currency,
                    "line_items": [
                        {
                            "description": item.description,
                            "quantity": item.quantity,
                            "unit_price": item.unit_price,
                            "amount": item.amount,
                        }
                        for item in extraction.line_items.all().order_by("line_number")
                    ],
                    "raw_text_evidence": extraction.raw_text_evidence or {},
                }
                val_result = val_engine.validate(val_payload)

                # Delete un-dismissed validation errors
                ValidationError.objects.filter(document=doc, is_dismissed=False).delete()
                for issue in (val_result.errors + val_result.warnings):
                    ValidationError.objects.create(
                        document=doc,
                        rule_id=str(issue.rule_id),
                        field=issue.field or "",
                        message=issue.message,
                        severity=issue.severity.value if hasattr(issue.severity, "value") else str(issue.severity),
                        actual_value=str(issue.actual) if issue.actual is not None else None,
                        expected_value=str(issue.expected) if issue.expected is not None else None,
                        difference=issue.difference,
                    )
                doc.validation_status = val_result.status.value
                doc.save(update_fields=["validation_status", "updated_at"])
            except Exception as val_exc:
                logger.warning(f"[API] Validation re-evaluation note: {val_exc}")

            # 6. Synchronize full-text search vector
            try:
                from apps.documents.search import update_document_search_vector
                update_document_search_vector(doc.id)
            except Exception as search_exc:
                logger.debug(f"[API] Search vector synchronization note: {search_exc}")

        # 7. Return complete updated document entity
        doc_detail = Document.objects.select_related("extraction").prefetch_related(
            "extraction__line_items",
            "validation_errors",
            "audit_logs",
        ).get(id=doc.id)
        return Response(DocumentDetailSerializer(doc_detail).data, status=status.HTTP_200_OK)


class CrossReconciliationViewSet(viewsets.ModelViewSet):
    """
    REST ViewSet managing cross-document financial verification and reconciliations.
    - list (GET /api/reconciliations/): Paginated listing of reconciliation records with filtering.
    - retrieve (GET /api/reconciliations/{id}/): Detailed findings, discrepancy list, and comparison matrix.
    - create (POST /api/reconciliations/): Trigger reconciliation between two documents.
    - re_reconcile (POST /api/reconciliations/{id}/re-reconcile/): Re-runs verification with fresh data.
    """
    permission_classes = [AllowAny]
    pagination_class = DocumentPagination
    serializer_class = CrossReconciliationSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = CrossReconciliation.objects.all().select_related(
            "doc_a", "doc_b",
            "doc_a__extraction", "doc_b__extraction",
        ).prefetch_related(
            "doc_a__extraction__line_items",
            "doc_b__extraction__line_items",
        )

        doc_id = self.request.query_params.get("document_id")
        if doc_id:
            try:
                uuid_obj = uuid.UUID(str(doc_id))
                qs = qs.filter(Q(doc_a_id=uuid_obj) | Q(doc_b_id=uuid_obj))
            except (ValueError, TypeError):
                pass

        recon_status = self.request.query_params.get("status")
        if recon_status:
            qs = qs.filter(status=recon_status.strip().upper())

        is_reconciled = self.request.query_params.get("is_reconciled")
        if is_reconciled is not None:
            if is_reconciled.lower() in ("true", "1"):
                qs = qs.filter(is_reconciled=True)
            elif is_reconciled.lower() in ("false", "0"):
                qs = qs.filter(is_reconciled=False)

        return qs.order_by("-created_at")

    def get_object(self) -> CrossReconciliation:
        pk_val = self.kwargs.get("pk", "")
        try:
            uuid_obj = uuid.UUID(str(pk_val))
        except (ValueError, TypeError, AttributeError):
            raise DRFValidationError({"error": f"Invalid reconciliation ID format '{pk_val}'. Expected UUID."})

        try:
            return self.get_queryset().get(id=uuid_obj)
        except CrossReconciliation.DoesNotExist:
            raise Http404(f"Reconciliation record with ID {pk_val} not found.")

    def _execute_and_persist_reconciliation(self, doc_a: Document, doc_b: Document, tolerance: Decimal) -> CrossReconciliation:
        from apps.documents.tasks import _format_model_extraction_to_dict
        from apps.validation.cross_verifier import CrossDocumentVerifier

        ext_a = getattr(doc_a, "extraction", None) or InvoiceExtraction.objects.filter(document=doc_a).first()
        ext_b = getattr(doc_b, "extraction", None) or InvoiceExtraction.objects.filter(document=doc_b).first()

        data_a = _format_model_extraction_to_dict(ext_a)
        data_b = _format_model_extraction_to_dict(ext_b)

        tol_decimal = Decimal(str(tolerance)) if tolerance else Decimal("0.05")
        verifier = CrossDocumentVerifier(default_tolerance=tol_decimal)
        result = verifier.reconcile(data_a, data_b, doc_a_id=str(doc_a.id), doc_b_id=str(doc_b.id))

        rec = CrossReconciliation.objects.create(
            doc_a=doc_a,
            doc_b=doc_b,
            status=result.status.value,
            is_reconciled=result.is_reconciled,
            discrepancies=[d.to_dict() for d in result.discrepancies],
            warnings=[w.to_dict() for w in result.warnings],
            fields_compared=result.fields_compared,
            matched_items_count=result.matched_items_count,
            unmatched_items_count=result.unmatched_items_count,
            summary=result.summary,
        )
        return rec

    def create(self, request: Request, *args, **kwargs) -> Response:
        """
        Initiates cross-document verification between doc_a and doc_b.
        Validates existence, distinctness, and structured extraction availability.
        Executes reconciliation and persists findings.
        """
        serializer = CrossReconciliationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        doc_a = serializer.validated_data["doc_a"]
        doc_b = serializer.validated_data["doc_b"]
        tolerance = serializer.validated_data.get("tolerance", Decimal("0.05"))

        # Guard against active processing state (409 Conflict)
        if doc_a.status == DocumentStatus.PROCESSING or doc_b.status == DocumentStatus.PROCESSING:
            return Response(
                {
                    "error": "Cannot reconcile documents while one or both are actively being processed.",
                    "doc_a_id": str(doc_a.id),
                    "doc_b_id": str(doc_b.id),
                },
                status=status.HTTP_409_CONFLICT,
            )

        logger.info(f"[API] Reconciling doc_a={doc_a.id} and doc_b={doc_b.id} (tolerance={tolerance})")

        rec = self._execute_and_persist_reconciliation(doc_a, doc_b, tolerance)
        return Response(CrossReconciliationSerializer(rec).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="re-reconcile")
    def re_reconcile(self, request: Request, pk=None) -> Response:
        """Re-runs reconciliation for an existing pair using latest document data and optional custom tolerance."""
        rec = self.get_object()
        raw_tol = request.data.get("tolerance")
        tolerance = Decimal(str(raw_tol)) if raw_tol is not None else Decimal("0.05")

        new_rec = self._execute_and_persist_reconciliation(rec.doc_a, rec.doc_b, tolerance)
        return Response(CrossReconciliationSerializer(new_rec).data, status=status.HTTP_201_CREATED)
