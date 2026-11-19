"""
Django Model Signals for Synchronizing Document Search Vectors.

Monitors lifecycle events across Document, InvoiceExtraction, and LineItem:
- Document creation / updates (filename, raw_text).
- InvoiceExtraction creation / updates (invoice_number, supplier_name, customer_name, addresses).
- InvoiceExtraction deletion (cleans up extraction data from document vector).
- LineItem creation / updates (description).
- LineItem deletion (removes deleted item descriptions from document vector).

Uses transaction.on_commit to ensure vector updates observe fully committed
database transactions and avoid premature queries or race conditions.
"""
import logging
from typing import Any

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.documents.models import Document, InvoiceExtraction, LineItem
from apps.documents.search import update_document_search_vector

logger = logging.getLogger(__name__)


def schedule_search_vector_update(doc_id: Any) -> None:
    """
    Schedules an update of the document search vector.
    Defers execution until the active transaction commits,
    or executes immediately if not within an atomic transaction.
    """
    if not doc_id:
        return

    try:
        conn = transaction.get_connection()
        if conn.in_atomic_block:
            transaction.on_commit(lambda: update_document_search_vector(doc_id))
        else:
            update_document_search_vector(doc_id)
    except Exception as exc:
        logger.debug(f"[Search Signals] Could not schedule search vector update for {doc_id}: {exc}")
        # Direct attempt fallback
        try:
            update_document_search_vector(doc_id)
        except Exception:
            pass


@receiver(post_save, sender=Document)
def on_document_saved(sender, instance, **kwargs):
    """Triggered when a Document is saved (creation, filename, or raw_text updates)."""
    schedule_search_vector_update(instance.id)


@receiver(post_save, sender=InvoiceExtraction)
def on_extraction_saved(sender, instance, **kwargs):
    """Triggered when an InvoiceExtraction is created or updated."""
    schedule_search_vector_update(instance.document_id)


@receiver(post_delete, sender=InvoiceExtraction)
def on_extraction_deleted(sender, instance, **kwargs):
    """Triggered when an InvoiceExtraction is deleted (e.g. reprocessing / reset)."""
    schedule_search_vector_update(instance.document_id)


@receiver(post_save, sender=LineItem)
def on_line_item_saved(sender, instance, **kwargs):
    """Triggered when a LineItem is created or updated."""
    if instance.extraction_id:
        try:
            doc_id = instance.extraction.document_id
            schedule_search_vector_update(doc_id)
        except Exception:
            pass


@receiver(post_delete, sender=LineItem)
def on_line_item_deleted(sender, instance, **kwargs):
    """Triggered when a LineItem is deleted."""
    if instance.extraction_id:
        try:
            doc_id = instance.extraction.document_id
            schedule_search_vector_update(doc_id)
        except Exception:
            pass
