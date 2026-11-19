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
from django.db.models import Q
from django.http import Http404
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
    ValidationError,
    ValidationStatusChoices,
)
from apps.documents.serializers import (
    CrossReconciliationRequestSerializer,
    CrossReconciliationSerializer,
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

        # 4. Search query (filename, invoice_number, supplier_name)
        search = self.request.query_params.get("search")
        if search:
            search_term = search.strip()
            qs = qs.filter(
                Q(filename__icontains=search_term)
                | Q(extraction__invoice_number__icontains=search_term)
                | Q(extraction__supplier_name__icontains=search_term)
            )

        # 5. Ordering
        ordering = self.request.query_params.get("ordering", "-created_at")
        allowed_ordering = {
            "created_at", "-created_at",
            "filename", "-filename",
            "status", "-status",
            "file_size_bytes", "-file_size_bytes",
        }
        if ordering in allowed_ordering:
            qs = qs.order_by(ordering)
        else:
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


class CrossReconciliationViewSet(viewsets.ModelViewSet):
    """
    REST ViewSet managing cross-document financial verification and reconciliations.
    - list (GET /api/reconciliations/): Paginated listing of reconciliation records.
    - retrieve (GET /api/reconciliations/{id}/): Detailed findings and discrepancy list.
    - create (POST /api/reconciliations/): Trigger reconciliation between two documents.
    """
    permission_classes = [AllowAny]
    pagination_class = DocumentPagination
    serializer_class = CrossReconciliationSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return CrossReconciliation.objects.all().select_related("doc_a", "doc_b").order_by("-created_at")

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

    def create(self, request: Request, *args, **kwargs) -> Response:
        """
        Initiates cross-document verification between doc_a and doc_b.
        Validates existence, distinctness, and structured extraction availability.
        """
        serializer = CrossReconciliationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        doc_a = serializer.validated_data["doc_a"]
        doc_b = serializer.validated_data["doc_b"]
        tolerance = serializer.validated_data.get("tolerance", Decimal("0.05"))

        logger.info(f"[API] Initiating cross-reconciliation between doc_a={doc_a.id} and doc_b={doc_b.id}")

        # Dispatch async reconciliation task
        task_res = reconcile_documents_task.delay(str(doc_a.id), str(doc_b.id), tolerance=str(tolerance))

        # Check if record was created immediately (e.g. eager mode in test / dev)
        rec = CrossReconciliation.objects.filter(doc_a=doc_a, doc_b=doc_b).order_by("-created_at").first()
        if rec:
            return Response(CrossReconciliationSerializer(rec).data, status=status.HTTP_201_CREATED)

        return Response(
            {
                "message": "Cross-document reconciliation task successfully queued.",
                "doc_a_id": str(doc_a.id),
                "doc_b_id": str(doc_b.id),
                "tolerance": str(tolerance),
            },
            status=status.HTTP_202_ACCEPTED,
        )
