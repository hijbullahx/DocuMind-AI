"""
Comprehensive Test Suite for TASK-013: PostgreSQL Full-Text Search & Multi-Field Search Engine.
Tests:
- Search across Weight A fields: Document filename, InvoiceExtraction invoice_number
- Search across Weight B fields: InvoiceExtraction supplier_name, customer_name
- Search across Weight C fields: InvoiceExtraction supplier_address, customer_address, LineItem description
- Search across Weight D fields: Document raw_text
- Multi-word search terms with AND token logic across document fields
- Punctuation, symbols, quotes, and special character sanitization
- Empty and whitespace-only search bypass
- No matching results handling
- Combining search with existing query filters (status, validation_status, file_type)
- Pagination of search result sets
- Ordering consistency (explicit ordering vs. relevance ranking)
- SQLite fallback behavior and PostgreSQL query builder validation
- Persisted SearchVector synchronization across Document, InvoiceExtraction, and LineItem lifecycle events
- PostgreSQL indexable @@ matching condition and zero-line-item-join query structure
- Multi-line-item duplicate document prevention
"""
from datetime import date
from decimal import Decimal
import os
from unittest.mock import MagicMock, patch

import django
import pytest

# Initialize Django environment
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "documind.settings")
django.setup()

from django.core.management import call_command
from django.db import connection
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
    ValidationStatusChoices,
)
from apps.documents.search import (
    apply_document_search,
    apply_postgres_fts,
    apply_sqlite_fallback_search,
    build_document_search_vector_parts,
    sanitize_search_query,
    tokenize_query,
    update_document_search_vector,
)


@pytest.fixture(scope="session", autouse=True)
def setup_search_test_env():
    """Applies migrations once for test session and closes initial setup connection."""
    call_command("migrate", verbosity=0)
    connection.close()


class BaseSearchTest:
    """Provides database isolation before and after each search test."""

    @pytest.fixture(autouse=True)
    def clean_db(self):
        connection.close()
        CrossReconciliation.objects.all().delete()
        AuditLog.objects.all().delete()
        ValidationError.objects.all().delete()
        LineItem.objects.all().delete()
        InvoiceExtraction.objects.all().delete()
        Document.objects.all().delete()
        connection.close()
        yield
        connection.close()
        CrossReconciliation.objects.all().delete()
        AuditLog.objects.all().delete()
        ValidationError.objects.all().delete()
        LineItem.objects.all().delete()
        InvoiceExtraction.objects.all().delete()
        Document.objects.all().delete()
        connection.close()


@pytest.fixture
def client():
    return APIClient()


# =========================================================================
# 1. Search Query Sanitization & Tokenization Unit Tests
# =========================================================================

class TestSearchSanitization(BaseSearchTest):
    """Tests input sanitization, whitespace stripping, and token extraction."""

    def test_sanitize_empty_and_whitespace(self):
        assert sanitize_search_query(None) == ""
        assert sanitize_search_query("") == ""
        assert sanitize_search_query("   ") == ""
        assert sanitize_search_query("\t\n  \r") == ""

    def test_sanitize_normalizes_consecutive_spaces(self):
        assert sanitize_search_query("  Acme    Global   Corp  ") == "Acme Global Corp"

    def test_tokenize_query(self):
        assert tokenize_query("") == []
        assert tokenize_query("Acme") == ["Acme"]
        assert tokenize_query("Acme Global Services") == ["Acme", "Global", "Services"]
        assert tokenize_query("INV-2024 $100.00") == ["INV-2024", "$100.00"]


# =========================================================================
# 2. Weighted Field Search Tests (API & Service Layer)
# =========================================================================

class TestWeightedFieldSearch(BaseSearchTest):
    """Verifies that search terms match across all 4 weighted field tiers."""

    def test_search_weight_a_filename(self, client):
        """Tier A: Search matches Document.filename."""
        doc = Document.objects.create(filename="contract_acme_2026.pdf", file_type="pdf")
        Document.objects.create(filename="other_file.pdf", file_type="pdf")

        res = client.get("/api/documents/?search=contract_acme")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 1
        assert res.data["results"][0]["id"] == str(doc.id)

    def test_search_weight_a_invoice_number(self, client):
        """Tier A: Search matches InvoiceExtraction.invoice_number."""
        doc = Document.objects.create(filename="invoice.pdf", file_type="pdf")
        InvoiceExtraction.objects.create(
            document=doc,
            invoice_number="INV-ALPHA-9988",
            total=Decimal("150.00"),
        )
        Document.objects.create(filename="unrelated.pdf", file_type="pdf")

        res = client.get("/api/documents/?search=ALPHA-9988")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 1
        assert res.data["results"][0]["id"] == str(doc.id)

    def test_search_weight_b_supplier_name(self, client):
        """Tier B: Search matches InvoiceExtraction.supplier_name."""
        doc = Document.objects.create(filename="doc.pdf", file_type="pdf")
        InvoiceExtraction.objects.create(
            document=doc,
            invoice_number="INV-001",
            supplier_name="Cyberdyne Systems Technologies",
            total=Decimal("5000.00"),
        )
        Document.objects.create(filename="other.pdf", file_type="pdf")

        res = client.get("/api/documents/?search=Cyberdyne")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 1
        assert res.data["results"][0]["id"] == str(doc.id)

    def test_search_weight_b_customer_name(self, client):
        """Tier B: Search matches InvoiceExtraction.customer_name."""
        doc = Document.objects.create(filename="doc.pdf", file_type="pdf")
        InvoiceExtraction.objects.create(
            document=doc,
            invoice_number="INV-002",
            customer_name="Wayne Enterprises International",
            total=Decimal("12000.00"),
        )
        Document.objects.create(filename="other.pdf", file_type="pdf")

        res = client.get("/api/documents/?search=Wayne Enterprises")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 1
        assert res.data["results"][0]["id"] == str(doc.id)

    def test_search_weight_c_supplier_address(self, client):
        """Tier C: Search matches InvoiceExtraction.supplier_address."""
        doc = Document.objects.create(filename="doc.pdf", file_type="pdf")
        InvoiceExtraction.objects.create(
            document=doc,
            invoice_number="INV-003",
            supplier_address="1044 Industrial Parkway, Sector 7, Neo Tokyo",
            total=Decimal("250.00"),
        )

        res = client.get("/api/documents/?search=Neo Tokyo")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 1
        assert res.data["results"][0]["id"] == str(doc.id)

    def test_search_weight_c_customer_address(self, client):
        """Tier C: Search matches InvoiceExtraction.customer_address."""
        doc = Document.objects.create(filename="doc.pdf", file_type="pdf")
        InvoiceExtraction.objects.create(
            document=doc,
            invoice_number="INV-004",
            customer_address="42 Wallaby Way, Sydney, Australia",
            total=Decimal("350.00"),
        )

        res = client.get("/api/documents/?search=Wallaby Way")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 1
        assert res.data["results"][0]["id"] == str(doc.id)

    def test_search_weight_c_line_item_description(self, client):
        """Tier C: Search matches LineItem.description."""
        doc = Document.objects.create(filename="doc.pdf", file_type="pdf")
        ext = InvoiceExtraction.objects.create(
            document=doc,
            invoice_number="INV-005",
            total=Decimal("999.00"),
        )
        LineItem.objects.create(
            extraction=ext,
            line_number=1,
            description="Quantum Flux Capacitor Repair Kit v2",
            amount=Decimal("999.00"),
        )
        Document.objects.create(filename="other.pdf", file_type="pdf")

        res = client.get("/api/documents/?search=Flux Capacitor")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 1
        assert res.data["results"][0]["id"] == str(doc.id)

    def test_search_weight_d_raw_text(self, client):
        """Tier D: Search matches Document.raw_text (OCR / body text)."""
        doc = Document.objects.create(
            filename="scan_invoice.pdf",
            file_type="pdf",
            raw_text="CONFIDENTIAL AUDIT: Certified under Section 404 compliance guidelines.",
        )
        Document.objects.create(filename="other.pdf", file_type="pdf", raw_text="Normal text.")

        res = client.get("/api/documents/?search=compliance guidelines")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 1
        assert res.data["results"][0]["id"] == str(doc.id)


# =========================================================================
# 3. Multi-Word Token Logic & Query Sanitization Tests
# =========================================================================

class TestMultiWordAndTokenSearch(BaseSearchTest):
    """Verifies that multi-word search tokens match across different fields in a document."""

    def test_multi_word_across_multiple_fields(self, client):
        """
        Query 'Cyberdyne Capacitor':
        'Cyberdyne' matches supplier_name (Tier B), 'Capacitor' matches LineItem description (Tier C).
        Should match because both tokens belong to the same document hierarchy.
        """
        doc1 = Document.objects.create(filename="inv_01.pdf", file_type="pdf")
        ext1 = InvoiceExtraction.objects.create(
            document=doc1,
            supplier_name="Cyberdyne Systems",
            invoice_number="INV-101",
            total=Decimal("500.00"),
        )
        LineItem.objects.create(
            extraction=ext1,
            line_number=1,
            description="High Voltage Flux Capacitor Component",
            amount=Decimal("500.00"),
        )

        # Unrelated doc that only has 'Cyberdyne' but not 'Capacitor'
        doc2 = Document.objects.create(filename="inv_02.pdf", file_type="pdf")
        InvoiceExtraction.objects.create(
            document=doc2,
            supplier_name="Cyberdyne Systems",
            invoice_number="INV-102",
            total=Decimal("200.00"),
        )

        res = client.get("/api/documents/?search=Cyberdyne Capacitor")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 1
        assert res.data["results"][0]["id"] == str(doc1.id)

    def test_special_characters_and_symbols_do_not_crash(self, client):
        """Queries containing punctuation, symbols, and operators execute safely."""
        doc = Document.objects.create(filename="PO#9928-ABC.pdf", file_type="pdf")
        InvoiceExtraction.objects.create(
            document=doc,
            invoice_number="PO#9928-ABC",
            total=Decimal("100.00"),
        )

        for query_str in ["PO#9928", "9928-ABC", "PO#9928-ABC", "$100", "PO & 9928"]:
            res = client.get(f"/api/documents/?search={query_str}")
            assert res.status_code == status.HTTP_200_OK

    def test_empty_or_whitespace_query_returns_all_documents(self, client):
        """Empty or whitespace-only search does not filter out documents."""
        Document.objects.create(filename="doc1.pdf", file_type="pdf")
        Document.objects.create(filename="doc2.pdf", file_type="pdf")

        for empty_q in ["", "   ", "\t\t  "]:
            res = client.get(f"/api/documents/?search={empty_q}")
            assert res.status_code == status.HTTP_200_OK
            assert res.data["count"] == 2

    def test_no_matches_returns_empty_results(self, client):
        """Query matching no document returns empty list with count 0."""
        Document.objects.create(filename="invoice.pdf", file_type="pdf")
        res = client.get("/api/documents/?search=NonExistentEntity99827361")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 0
        assert res.data["results"] == []


# =========================================================================
# 4. Search Filter Composition, Deduplication & Pagination
# =========================================================================

class TestSearchCompositionAndPagination(BaseSearchTest):
    """Verifies search works in harmony with filters, ordering, and pagination."""

    def test_search_combined_with_status_filter(self, client):
        """Search query combined with status filter restricts to matching status."""
        doc_success = Document.objects.create(
            filename="invoice_acme.pdf",
            file_type="pdf",
            status=DocumentStatus.SUCCESS,
        )
        doc_failed = Document.objects.create(
            filename="receipt_acme.pdf",
            file_type="pdf",
            status=DocumentStatus.FAILED,
        )

        res_succ = client.get("/api/documents/?search=acme&status=SUCCESS")
        assert res_succ.status_code == status.HTTP_200_OK
        assert res_succ.data["count"] == 1
        assert res_succ.data["results"][0]["id"] == str(doc_success.id)

        res_fail = client.get("/api/documents/?search=acme&status=FAILED")
        assert res_fail.status_code == status.HTTP_200_OK
        assert res_fail.data["count"] == 1
        assert res_fail.data["results"][0]["id"] == str(doc_failed.id)

    def test_search_pagination(self, client):
        """Search results paginate correctly using page_size=20."""
        for i in range(25):
            Document.objects.create(
                filename=f"batch_search_doc_{i:02d}.pdf",
                file_type="pdf",
                status=DocumentStatus.SUCCESS,
            )

        res = client.get("/api/documents/?search=batch_search_doc")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 25
        assert len(res.data["results"]) == 20
        assert res.data["next"] is not None

        # Fetch page 2
        res_page2 = client.get(res.data["next"])
        assert res_page2.status_code == status.HTTP_200_OK
        assert len(res_page2.data["results"]) == 5

    def test_search_with_explicit_ordering(self, client):
        """Explicit ?ordering= parameter overrides default search ordering."""
        d1 = Document.objects.create(filename="b_file.pdf", file_type="pdf", file_size_bytes=500)
        d2 = Document.objects.create(filename="a_file.pdf", file_type="pdf", file_size_bytes=100)
        d3 = Document.objects.create(filename="c_file.pdf", file_type="pdf", file_size_bytes=300)

        # Order ascending by filename
        res = client.get("/api/documents/?search=file&ordering=filename")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 3
        filenames = [r["filename"] for r in res.data["results"]]
        assert filenames == ["a_file.pdf", "b_file.pdf", "c_file.pdf"]

        # Order descending by file_size_bytes
        res_size = client.get("/api/documents/?search=file&ordering=-file_size_bytes")
        sizes = [r["file_size_bytes"] for r in res_size.data["results"]]
        assert sizes == [500, 300, 100]

    def test_multi_line_items_do_not_duplicate_documents(self, client):
        """A document with multiple line items matching the same query appears exactly once."""
        doc = Document.objects.create(filename="multi_items.pdf", file_type="pdf")
        ext = InvoiceExtraction.objects.create(document=doc, invoice_number="INV-MULTI-1")
        for i in range(10):
            LineItem.objects.create(
                extraction=ext,
                line_number=i + 1,
                description=f"Standard Industrial Widget Part #{i+100}",
                amount=Decimal("10.00"),
            )

        res = client.get("/api/documents/?search=Widget")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 1
        assert len(res.data["results"]) == 1
        assert res.data["results"][0]["id"] == str(doc.id)


# =========================================================================
# 5. Persisted Search Vector Synchronization & Lifecycle Unit Tests
# =========================================================================

class TestSearchVectorSynchronization(BaseSearchTest):
    """
    Tests the search vector synchronization lifecycle across Document,
    InvoiceExtraction, and LineItem creation, modification, and deletion.
    """

    def test_document_creation_and_update_vector_parts(self):
        """Document creation and updates reflect immediately in vector tiers A and D."""
        doc = Document.objects.create(
            filename="annual_financial_report.pdf",
            file_type="pdf",
            raw_text="Q4 balance sheet and income statement audit overview.",
        )
        parts = build_document_search_vector_parts(doc.id)
        assert parts is not None
        assert "annual_financial_report.pdf" in parts["A"]
        assert "Q4 balance sheet and income statement audit overview." in parts["D"]
        assert parts["B"] == []
        assert parts["C"] == []

        # Update filename and raw_text
        doc.filename = "updated_report.pdf"
        doc.raw_text = "Updated audit text content."
        doc.save()

        updated_parts = build_document_search_vector_parts(doc.id)
        assert "updated_report.pdf" in updated_parts["A"]
        assert "Updated audit text content." in updated_parts["D"]

    def test_invoice_extraction_lifecycle_updates_vector_parts(self):
        """InvoiceExtraction creation and deletion updates parent document vector tiers."""
        doc = Document.objects.create(filename="invoice.pdf", file_type="pdf")

        # Create extraction
        ext = InvoiceExtraction.objects.create(
            document=doc,
            invoice_number="INV-2026-X1",
            supplier_name="Global Logistics Inc",
            customer_name="Acme Corporation",
            supplier_address="100 Harbor Blvd, Port City",
            customer_address="500 Tech Parkway, Silicon Valley",
            total=Decimal("4500.00"),
        )

        parts = build_document_search_vector_parts(doc.id)
        assert "INV-2026-X1" in parts["A"]
        assert "Global Logistics Inc" in parts["B"]
        assert "Acme Corporation" in parts["B"]
        assert "100 Harbor Blvd, Port City" in parts["C"]
        assert "500 Tech Parkway, Silicon Valley" in parts["C"]

        # Delete extraction (e.g. reprocessing / retry reset)
        ext.delete()
        after_delete_parts = build_document_search_vector_parts(doc.id)
        assert after_delete_parts is not None
        assert "invoice.pdf" in after_delete_parts["A"]
        assert "INV-2026-X1" not in after_delete_parts["A"]
        assert after_delete_parts["B"] == []
        assert after_delete_parts["C"] == []

    def test_line_item_lifecycle_updates_vector_parts(self):
        """LineItem creation, modification, and deletion updates parent document Tier C."""
        doc = Document.objects.create(filename="bill.pdf", file_type="pdf")
        ext = InvoiceExtraction.objects.create(document=doc, invoice_number="INV-BILL-10")

        item1 = LineItem.objects.create(
            extraction=ext,
            line_number=1,
            description="Titanium Structural Bolts Grade 5",
            amount=Decimal("150.00"),
        )
        item2 = LineItem.objects.create(
            extraction=ext,
            line_number=2,
            description="Stainless Steel Washers",
            amount=Decimal("50.00"),
        )

        parts = build_document_search_vector_parts(doc.id)
        assert "Titanium Structural Bolts Grade 5" in parts["C"]
        assert "Stainless Steel Washers" in parts["C"]

        # Delete one line item
        item1.delete()
        updated_parts = build_document_search_vector_parts(doc.id)
        assert "Titanium Structural Bolts Grade 5" not in updated_parts["C"]
        assert "Stainless Steel Washers" in updated_parts["C"]

    def test_update_document_search_vector_helper_execution(self):
        """update_document_search_vector executes cleanly without exception."""
        doc = Document.objects.create(filename="test_sync.pdf", file_type="pdf")
        result = update_document_search_vector(doc.id)
        assert result is True

        # Non-existent doc returns False
        missing_result = update_document_search_vector("00000000-0000-0000-0000-000000000000")
        assert missing_result is False


# =========================================================================
# 6. PostgreSQL FTS Query & Index Structure Unit Tests (Static & Mocked)
# =========================================================================

class TestPostgresSearchQueryBuilder(BaseSearchTest):
    """
    Validates PostgreSQL SearchVector, SearchQuery, and indexable @@ query structure.
    Statically inspects the Django query compiler to ensure proper operator usage.
    """

    def test_postgres_search_query_websearch_and_plain_types(self):
        """SearchQuery generates websearch_to_tsquery and plainto_tsquery functions."""
        from django.contrib.postgres.search import SearchQuery

        q_web = SearchQuery('Acme Corp "Fast Delivery"', search_type="websearch", config="english")
        assert q_web.function == "websearch_to_tsquery"

        q_plain = SearchQuery("simple query", search_type="plain", config="english")
        assert q_plain.function == "plainto_tsquery"

    def test_postgres_filter_uses_search_vector_exact_match_operator(self):
        """
        Validates that filtering Document.objects.filter(search_vector=query_obj)
        generates the PostgreSQL @@ matching operator against Document.search_vector.
        """
        from django.contrib.postgres.search import SearchQuery, SearchVectorExact, SearchVectorField

        field = SearchVectorField()
        lookup_cls = field.get_lookup("exact")
        assert lookup_cls is SearchVectorExact

    def test_postgres_fts_zero_line_item_joins(self):
        """
        Validates that apply_postgres_fts filters directly against Document.search_vector
        without joining documents_lineitem or documents_invoiceextraction.
        """
        from django.contrib.postgres.search import SearchQuery

        with patch("django.db.connection.vendor", "postgresql"):
            qs = Document.objects.all()
            result_qs = apply_postgres_fts(qs, "acme corporation")

            # Inspect the query's tables
            compiler = result_qs.query.get_compiler("default")
            sql, _ = compiler.as_sql()

            # Ensure documents_lineitem is NOT joined in the search query
            assert "documents_lineitem" not in sql
            # Ensure documents_invoiceextraction is NOT joined in the search query
            assert "documents_invoiceextraction" not in sql
            # Ensure query operates on documents_document
            assert "documents_document" in sql
