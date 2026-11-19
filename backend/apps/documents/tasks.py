"""
Celery Asynchronous Tasks for Document Ingestion, AI Extraction, and Validation.
Coordinates the end-to-end processing pipeline for documents in background workers,
managing status transitions, error handling, idempotency guards, and database persistence.
"""
from decimal import Decimal
import json
import logging
import os
from typing import Any, Dict, List, Optional, Union
import uuid

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.documents.models import (
    AuditLog,
    CrossReconciliation,
    Document,
    DocumentStatus,
    InvoiceExtraction as ModelInvoiceExtraction,
    LineItem as ModelLineItem,
    ValidationError as ModelValidationError,
    ValidationSeverityChoices,
    ValidationStatusChoices,
)
from apps.extraction.llm_client import (
    BaseLLMProvider,
    ExtractionResultStatus,
    GeminiProvider,
    LLMExtractionClient,
    MockLLMProvider,
    OpenAIProvider,
)
from apps.extraction.schemas import InvoiceExtraction as PydanticInvoiceExtraction
from apps.ingestion.base import ExtractionStatus
from apps.ingestion.ingestion_service import DocumentIngestionService
from apps.validation.cross_verifier import CrossDocumentVerifier
from apps.validation.engine import ValidationEngine

logger = logging.getLogger(__name__)


DEFAULT_MOCK_INVOICE_JSON = json.dumps({
    "invoice_number": "INV-MOCK-001",
    "invoice_date": "2024-05-01",
    "due_date": "2024-05-31",
    "supplier_name": "Mock Supplier LLC",
    "supplier_address": "123 Mock Street, Suite 100",
    "customer_name": "Mock Customer Inc",
    "customer_address": "456 Client Ave",
    "subtotal": "100.00",
    "tax": "10.00",
    "total": "110.00",
    "currency": "USD",
    "line_items": [
        {
            "description": "Consulting Services",
            "quantity": "2",
            "unit_price": "50.00",
            "amount": "100.00",
        }
    ],
    "raw_text_evidence": {
        "invoice_number": "INV-MOCK-001",
        "total": "110.00",
    },
})


def _get_llm_provider(
    provider_name: Optional[Union[str, BaseLLMProvider]],
    canned_response: Optional[str] = None,
) -> Optional[BaseLLMProvider]:
    """Resolves the LLM provider instance from a string name or returns an explicit provider instance."""
    mock_canned = canned_response or DEFAULT_MOCK_INVOICE_JSON

    if provider_name is None:
        configured = os.environ.get("DOCUMIND_LLM_PROVIDER", "").strip().lower()
        if configured == "mock":
            return MockLLMProvider(canned_response=mock_canned)
        return None  # Let LLMExtractionClient use default settings

    if isinstance(provider_name, BaseLLMProvider):
        return provider_name

    p_str = str(provider_name).strip().lower()
    if p_str == "mock":
        return MockLLMProvider(canned_response=mock_canned)
    elif p_str == "gemini":
        return GeminiProvider()
    elif p_str == "openai":
        return OpenAIProvider()
    else:
        logger.warning(f"Unrecognized LLM provider '{provider_name}'. Falling back to default.")
        return None


def _format_model_extraction_to_dict(extraction: ModelInvoiceExtraction) -> Dict[str, Any]:
    """Formats a database ModelInvoiceExtraction into a dictionary compatible with CrossDocumentVerifier."""
    return {
        "invoice_number": extraction.invoice_number,
        "invoice_date": extraction.invoice_date.isoformat() if extraction.invoice_date else None,
        "due_date": extraction.due_date.isoformat() if extraction.due_date else None,
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
                "line_number": li.line_number,
                "description": li.description,
                "quantity": li.quantity,
                "unit_price": li.unit_price,
                "amount": li.amount,
            }
            for li in extraction.line_items.all().order_by("line_number")
        ],
    }


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=5,
    name="apps.documents.tasks.process_document_task",
)
def process_document_task(
    self,
    document_id: str,
    force: bool = False,
    provider: Optional[str] = None,
    canned_response: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Asynchronous Celery task orchestrating the end-to-end processing pipeline for a Document.
    1. Ingestion: parses raw document file or consumes pre-loaded raw_text.
    2. Extraction: executes zero-hallucination structured financial extraction via LLMExtractionClient.
    3. Validation: runs deterministic mathematical rules, anomaly checks, and duplicate detection.
    4. Persistence: saves structured records and validation findings atomically in PostgreSQL.
    """
    logger.info(f"[Celery] Starting process_document_task for document_id={document_id} (force={force})")

    # 1. Validate UUID and fetch target document
    try:
        uuid_obj = uuid.UUID(str(document_id))
    except (ValueError, TypeError, AttributeError):
        logger.error(f"[Celery] Malformed UUID string provided for document_id: '{document_id}'")
        return {"success": False, "error": f"Invalid document_id UUID format: {document_id}"}

    try:
        doc = Document.objects.filter(id=uuid_obj).first()
    except Exception as exc:
        logger.error(f"[Celery] Database error fetching document {uuid_obj}: {exc}")
        return {"success": False, "error": f"Database query error: {exc}"}

    if not doc:
        logger.warning(f"[Celery] Document {document_id} not found in database.")
        return {"success": False, "error": f"Document {document_id} not found."}

    # 2. Idempotency guard & Atomic Claim
    previous_status = doc.status

    if not force:
        # Rejection: already actively processing
        if doc.status == DocumentStatus.PROCESSING:
            logger.info(f"[Celery] Document {document_id} is already in PROCESSING status. Skipping.")
            return {
                "success": False,
                "document_id": str(doc.id),
                "status": doc.status,
                "message": "Document is already being processed.",
            }

        # Rejection: already successfully processed
        if doc.status == DocumentStatus.SUCCESS:
            logger.info(f"[Celery] Document {document_id} is already SUCCESS. Skipping.")
            return {
                "success": True,
                "document_id": str(doc.id),
                "status": doc.status,
                "message": "Document has already been successfully processed.",
            }

        # Atomic conditional claim: transition from QUEUED (or retry of FAILED) to PROCESSING.
        # Uses database-level atomic conditional UPDATE to prevent multi-worker claim races.
        claimable_statuses = [DocumentStatus.QUEUED]
        if getattr(self.request, "retries", 0) > 0:
            claimable_statuses.append(DocumentStatus.FAILED)

        claimed_count = Document.objects.filter(
            id=uuid_obj,
            status__in=claimable_statuses,
        ).update(
            status=DocumentStatus.PROCESSING,
            error_message=None,
            updated_at=timezone.now(),
        )

        if claimed_count == 0:
            doc.refresh_from_db()
            logger.info(
                f"[Celery] Document {document_id} could not be claimed for processing (current status: {doc.status}). Skipping."
            )
            if doc.status == DocumentStatus.PROCESSING:
                return {
                    "success": False,
                    "document_id": str(doc.id),
                    "status": doc.status,
                    "message": "Document is already being processed.",
                }
            elif doc.status == DocumentStatus.SUCCESS:
                return {
                    "success": True,
                    "document_id": str(doc.id),
                    "status": doc.status,
                    "message": "Document has already been successfully processed.",
                }
            else:
                return {
                    "success": False,
                    "document_id": str(doc.id),
                    "status": doc.status,
                    "message": f"Document could not be claimed for processing (current status: {doc.status}).",
                }

    else:
        # force=True: Re-processing requested.
        # Ensure forced reprocessing does not create unsafe concurrent processing:
        # Cannot claim if another worker is currently in PROCESSING status.
        if doc.status == DocumentStatus.PROCESSING:
            logger.info(
                f"[Celery] Document {document_id} is currently in PROCESSING status. Forced claim rejected."
            )
            return {
                "success": False,
                "document_id": str(doc.id),
                "status": doc.status,
                "message": "Document is already being processed.",
            }

        claimed_count = Document.objects.filter(
            id=uuid_obj,
        ).exclude(
            status=DocumentStatus.PROCESSING,
        ).update(
            status=DocumentStatus.PROCESSING,
            error_message=None,
            updated_at=timezone.now(),
        )

        if claimed_count == 0:
            doc.refresh_from_db()
            logger.info(
                f"[Celery] Forced claim failed for document {document_id}; current status={doc.status}. Skipping."
            )
            return {
                "success": False,
                "document_id": str(doc.id),
                "status": doc.status,
                "message": "Document is already being processed.",
            }

        if previous_status in (DocumentStatus.SUCCESS, DocumentStatus.PARTIAL_SUCCESS, DocumentStatus.FAILED):
            AuditLog.objects.create(
                document=doc,
                user_id="celery_worker",
                action="REPROCESS",
                reason=f"Reprocessing initiated (previous status: {previous_status})",
            )

    # Refresh the in-memory document instance with the claimed PROCESSING state
    doc.refresh_from_db()

    try:
        # 3. Stage 1: Document Ingestion
        ingestion_service = DocumentIngestionService()
        has_file = bool(doc.file and doc.file.name)

        if has_file:
            logger.info(f"[Celery] Ingesting file for doc {doc.id} ({doc.filename})")
            # Determine path or bytes
            file_bytes = None
            try:
                if hasattr(doc.file, "path") and os.path.exists(doc.file.path):
                    ingest_input = doc.file.path
                else:
                    doc.file.open("rb")
                    file_bytes = doc.file.read()
                    ingest_input = file_bytes
            except Exception:
                doc.file.open("rb")
                file_bytes = doc.file.read()
                ingest_input = file_bytes

            ingestion_result = ingestion_service.ingest(ingest_input, filename=doc.filename)

            if ingestion_result.status in (ExtractionStatus.EMPTY, ExtractionStatus.FAILED) and not doc.raw_text:
                err_msg = ingestion_result.error_message or "Document ingestion failed"
                logger.error(f"[Celery] Ingestion failed for doc {doc.id}: {err_msg}")
                doc.status = DocumentStatus.FAILED
                doc.validation_status = ValidationStatusChoices.FAILED
                doc.error_message = err_msg
                doc.save(update_fields=["status", "validation_status", "error_message", "updated_at"])
                return {"success": False, "document_id": str(doc.id), "status": doc.status, "error": err_msg}

            # Update document with ingested text and metadata
            if ingestion_result.full_text:
                doc.raw_text = ingestion_result.full_text
            if ingestion_result.metadata and ingestion_result.metadata.page_count:
                doc.page_count = max(ingestion_result.metadata.page_count, 1)

            # Merge metadata
            current_meta = dict(doc.metadata or {})
            current_meta["ingestion_status"] = ingestion_result.status.value
            current_meta["processing_time_ms"] = ingestion_result.processing_time_ms
            current_meta["tables_extracted"] = ingestion_result.tables_extracted
            if ingestion_result.ocr_warnings:
                current_meta["ocr_warnings"] = ingestion_result.ocr_warnings
            doc.metadata = current_meta

        elif not doc.raw_text:
            err_msg = "Document has neither an attached file nor raw_text content."
            logger.error(f"[Celery] {err_msg} for doc {doc.id}")
            doc.status = DocumentStatus.FAILED
            doc.validation_status = ValidationStatusChoices.FAILED
            doc.error_message = err_msg
            doc.save(update_fields=["status", "validation_status", "error_message", "updated_at"])
            return {"success": False, "document_id": str(doc.id), "status": doc.status, "error": err_msg}

        # 4. Stage 2: AI Financial Extraction
        logger.info(f"[Celery] Extracting financial entities for doc {doc.id}")
        provider_instance = _get_llm_provider(provider, canned_response=canned_response)
        llm_client = LLMExtractionClient(provider=provider_instance)

        extraction_result = llm_client.extract(doc.raw_text)

        if extraction_result.status != ExtractionResultStatus.SUCCESS or not extraction_result.invoice:
            err_msg = extraction_result.error_message or f"AI extraction failed with status: {extraction_result.status.value}"
            logger.error(f"[Celery] Extraction failed for doc {doc.id}: {err_msg}")
            doc.status = DocumentStatus.FAILED
            doc.validation_status = ValidationStatusChoices.FAILED
            doc.error_message = err_msg
            doc.save(update_fields=["status", "validation_status", "error_message", "updated_at"])
            return {"success": False, "document_id": str(doc.id), "status": doc.status, "error": err_msg}

        extracted_invoice = extraction_result.invoice

        # 5. Stage 3: Deterministic Financial Validation & Duplicate Check
        logger.info(f"[Celery] Validating extracted data for doc {doc.id}")
        validation_engine = ValidationEngine()

        def _is_db_duplicate(supplier: str, inv_number: str) -> bool:
            """Checks existing persisted extractions in PostgreSQL for duplicate invoice identifiers."""
            return ModelInvoiceExtraction.objects.filter(
                supplier_name__iexact=supplier.strip(),
                invoice_number__iexact=inv_number.strip(),
            ).exclude(document_id=doc.id).exists()

        validation_result = validation_engine.validate(
            invoice_data=extracted_invoice,
            is_duplicate_fn=_is_db_duplicate,
        )

        # 6. Stage 4: Atomic Database Persistence
        with transaction.atomic():
            # Update or create InvoiceExtraction
            invoice_rec, _ = ModelInvoiceExtraction.objects.update_or_create(
                document=doc,
                defaults={
                    "invoice_number": extracted_invoice.invoice_number,
                    "invoice_date": extracted_invoice.invoice_date,
                    "due_date": extracted_invoice.due_date,
                    "supplier_name": extracted_invoice.supplier_name,
                    "supplier_address": extracted_invoice.supplier_address,
                    "customer_name": extracted_invoice.customer_name,
                    "customer_address": extracted_invoice.customer_address,
                    "subtotal": extracted_invoice.subtotal,
                    "tax": extracted_invoice.tax,
                    "total": extracted_invoice.total,
                    "currency": extracted_invoice.currency,
                    "raw_text_evidence": extracted_invoice.raw_text_evidence or {},
                    "confidence_score": extraction_result.confidence_score,
                    "llm_model": extraction_result.model,
                },
            )

            # Re-create line items
            invoice_rec.line_items.all().delete()
            for idx, item in enumerate(extracted_invoice.line_items, start=1):
                ModelLineItem.objects.create(
                    extraction=invoice_rec,
                    line_number=idx,
                    description=item.description,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    amount=item.amount,
                )

            # Delete un-dismissed validation errors for this document
            ModelValidationError.objects.filter(document=doc, is_dismissed=False).delete()

            # Record newly identified validation errors and warnings
            for issue in (validation_result.errors + validation_result.warnings):
                ModelValidationError.objects.create(
                    document=doc,
                    rule_id=str(issue.rule_id),
                    field=issue.field or "",
                    message=issue.message,
                    severity=issue.severity.value if hasattr(issue.severity, "value") else str(issue.severity),
                    actual_value=str(issue.actual) if issue.actual is not None else None,
                    expected_value=str(issue.expected) if issue.expected is not None else None,
                    difference=issue.difference,
                )

            # Update final Document state
            doc.validation_status = validation_result.status.value
            doc.status = DocumentStatus.SUCCESS
            doc.error_message = None
            doc.save(
                update_fields=[
                    "status",
                    "validation_status",
                    "error_message",
                    "raw_text",
                    "page_count",
                    "metadata",
                    "updated_at",
                ]
            )

        logger.info(
            f"[Celery] Successfully processed doc {doc.id}: status={doc.status}, "
            f"validation_status={doc.validation_status}, errors={len(validation_result.errors)}, "
            f"warnings={len(validation_result.warnings)}"
        )
        return {
            "success": True,
            "document_id": str(doc.id),
            "status": doc.status,
            "validation_status": doc.validation_status,
            "invoice_number": extracted_invoice.invoice_number,
            "errors_count": len(validation_result.errors),
            "warnings_count": len(validation_result.warnings),
        }

    except Exception as exc:
        logger.exception(f"[Celery] Unhandled exception processing document {document_id}: {exc}")
        try:
            doc.refresh_from_db()
            doc.status = DocumentStatus.FAILED
            doc.validation_status = ValidationStatusChoices.FAILED
            doc.error_message = str(exc)
            doc.save(update_fields=["status", "validation_status", "error_message", "updated_at"])
        except Exception as save_exc:
            logger.error(f"[Celery] Failed to record failure state for document {document_id}: {save_exc}")

        # Check for retry eligibility if transient network/operational error
        if self.request.retries < self.max_retries and not isinstance(exc, (ValueError, TypeError)):
            logger.info(f"[Celery] Retrying document task (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=exc, countdown=2 ** self.request.retries)

        return {
            "success": False,
            "document_id": str(doc.id),
            "status": DocumentStatus.FAILED,
            "error": str(exc),
        }


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=5,
    name="apps.documents.tasks.reconcile_documents_task",
)
def reconcile_documents_task(
    self,
    doc_a_id: str,
    doc_b_id: str,
    tolerance: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Asynchronous Celery task orchestrating cross-document verification between two documents.
    Compares structured extractions for doc_a and doc_b, recording discrepancies and match counts.
    """
    logger.info(f"[Celery] Starting reconcile_documents_task between doc_a={doc_a_id} and doc_b={doc_b_id}")

    if str(doc_a_id) == str(doc_b_id):
        err = "Cross-reconciliation requires two distinct documents; self-reconciliation is not permitted."
        return {"success": False, "error": err}

    try:
        uuid_a = uuid.UUID(str(doc_a_id))
        uuid_b = uuid.UUID(str(doc_b_id))
    except (ValueError, TypeError, AttributeError):
        return {"success": False, "error": "Invalid document UUID format provided for cross-reconciliation."}

    try:
        doc_a = Document.objects.filter(id=uuid_a).first()
        doc_b = Document.objects.filter(id=uuid_b).first()
    except Exception as exc:
        return {"success": False, "error": f"Error fetching documents: {exc}"}

    if not doc_a:
        return {"success": False, "error": f"Document A ({doc_a_id}) not found."}
    if not doc_b:
        return {"success": False, "error": f"Document B ({doc_b_id}) not found."}

    ext_a = getattr(doc_a, "extraction", None) or ModelInvoiceExtraction.objects.filter(document=doc_a).first()
    ext_b = getattr(doc_b, "extraction", None) or ModelInvoiceExtraction.objects.filter(document=doc_b).first()

    if not ext_a:
        return {"success": False, "error": f"Document A ({doc_a.filename}) has no structured extraction record."}
    if not ext_b:
        return {"success": False, "error": f"Document B ({doc_b.filename}) has no structured extraction record."}

    data_a = _format_model_extraction_to_dict(ext_a)
    data_b = _format_model_extraction_to_dict(ext_b)

    tol_decimal = Decimal(tolerance) if tolerance else Decimal("0.05")
    verifier = CrossDocumentVerifier(default_tolerance=tol_decimal)
    result = verifier.reconcile(data_a, data_b, doc_a_id=str(doc_a.id), doc_b_id=str(doc_b.id))

    try:
        reconciliation_rec = CrossReconciliation.objects.create(
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
    except Exception as exc:
        logger.exception(f"[Celery] Error persisting CrossReconciliation: {exc}")
        return {"success": False, "error": f"Failed to persist reconciliation: {exc}"}

    logger.info(
        f"[Celery] Reconciled {doc_a.id} vs {doc_b.id}: status={reconciliation_rec.status}, "
        f"is_reconciled={reconciliation_rec.is_reconciled}"
    )
    return {
        "success": True,
        "reconciliation_id": str(reconciliation_rec.id),
        "status": reconciliation_rec.status,
        "is_reconciled": reconciliation_rec.is_reconciled,
        "discrepancies_count": len(result.discrepancies),
        "warnings_count": len(result.warnings),
        "matched_items": result.matched_items_count,
        "unmatched_items": result.unmatched_items_count,
        "summary": result.summary,
    }
