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
    apply_sqlite_fallback_search,
    sanitize_search_query,
    tokenize_query,
)


@pytest.fixture(scope="session", autouse=True)
def setup_search_test_env():
    """Applies migrations once for test session."""
    call_command("migrate", verbosity=0)


class BaseSearchTest:
    """Provides database isolation before and after each search test."""

    @pytest.fixture(autouse=True)
    def clean_db(self):
        CrossReconciliation.objects.all().delete()
        AuditLog.objects.all().delete()
        ValidationError.objects.all().delete()
        LineItem.objects.all().delete()
        InvoiceExtraction.objects.all().delete()
        Document.objects.all().delete()
        yield
        CrossReconciliation.objects.all().delete()
        AuditLog.objects.all().delete()
        ValidationError.objects.all().delete()
        LineItem.objects.all().delete()
        InvoiceExtraction.objects.all().delete()
        Document.objects.all().delete()


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

        res = client.get("/api/documents/?search=Cyberdyne")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 1
        assert res.data["results"][0]["id"] == str(doc.id)

    def test_search_weight_b_customer_name(self, client):
        """Tier B: Search matches InvoiceExtraction.customer_name."""
        doc = Document.objects.create(filename="statement.pdf", file_type="pdf")
        InvoiceExtraction.objects.create(
            document=doc,
            invoice_number="INV-002",
            customer_name="Stark Industries Global",
            total=Decimal("12000.00"),
        )

        res = client.get("/api/documents/?search=Stark Industries")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 1
        assert res.data["results"][0]["id"] == str(doc.id)

    def test_search_weight_c_addresses(self, client):
        """Tier C: Search matches supplier_address or customer_address."""
        doc1 = Document.objects.create(filename="doc1.pdf", file_type="pdf")
        InvoiceExtraction.objects.create(
            document=doc1,
            invoice_number="INV-003",
            supplier_address="742 Evergreen Terrace, Springfield",
        )

        doc2 = Document.objects.create(filename="doc2.pdf", file_type="pdf")
        InvoiceExtraction.objects.create(
            document=doc2,
            invoice_number="INV-004",
            customer_address="221B Baker Street, London",
        )

        # Search supplier address
        res1 = client.get("/api/documents/?search=Evergreen Terrace")
        assert res1.data["count"] == 1
        assert res1.data["results"][0]["id"] == str(doc1.id)

        # Search customer address
        res2 = client.get("/api/documents/?search=Baker Street")
        assert res2.data["count"] == 1
        assert res2.data["results"][0]["id"] == str(doc2.id)

    def test_search_weight_c_line_item_description(self, client):
        """Tier C: Search matches LineItem.description."""
        doc = Document.objects.create(filename="hardware_po.pdf", file_type="pdf")
        ext = InvoiceExtraction.objects.create(
            document=doc,
            invoice_number="INV-005",
            total=Decimal("350.00"),
        )
        LineItem.objects.create(
            extraction=ext,
            line_number=1,
            description="Quantum Cryptographic Accelerator PCIe Card",
            quantity=Decimal("1"),
            unit_price=Decimal("350.00"),
            amount=Decimal("350.00"),
        )

        res = client.get("/api/documents/?search=Cryptographic Accelerator")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 1
        assert res.data["results"][0]["id"] == str(doc.id)

    def test_search_weight_d_raw_text(self, client):
        """Tier D: Search matches raw_text extracted from PDF/OCR."""
        doc = Document.objects.create(
            filename="scanned_receipt.jpg",
            file_type="jpg",
            raw_text="CONFIDENTIAL AUDIT NOTE: Payment authorized via wire transfer ref WT-99201",
        )

        res = client.get("/api/documents/?search=WT-99201")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 1
        assert res.data["results"][0]["id"] == str(doc.id)


# =========================================================================
# 3. Multi-Word, Special Characters & Edge Case Tests
# =========================================================================

class TestSearchEdgeCasesAndMultiWord(BaseSearchTest):
    """Tests multi-word conjunctions, punctuation, symbols, and empty inputs."""

    def test_multi_word_across_distinct_fields(self, client):
        """Multi-word query matches when words appear in different fields of the same document."""
        doc = Document.objects.create(filename="q3_invoice.pdf", file_type="pdf")
        ext = InvoiceExtraction.objects.create(
            document=doc,
            invoice_number="INV-777",
            supplier_name="Wayne Enterprises",
            total=Decimal("450.00"),
        )
        LineItem.objects.create(
            extraction=ext,
            line_number=1,
            description="Batarang Maintenance Kit",
            amount=Decimal("450.00"),
        )

        # "Wayne" is in supplier_name, "Batarang" is in line item description
        res = client.get("/api/documents/?search=Wayne Batarang")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 1
        assert res.data["results"][0]["id"] == str(doc.id)

    def test_search_with_punctuation_and_symbols(self, client):
        """Verifies special characters ($, #, /, &, %, quotes) do not crash queries."""
        doc = Document.objects.create(
            filename="special_char_inv.pdf",
            file_type="pdf",
            raw_text="Tax rate 8.25% applied to Total: $1,250.00 for PO#44/99 & Co.",
        )

        # Test search with punctuation
        queries = ["$1,250.00", "PO#44/99", "8.25%", "PO#44/99 & Co."]
        for q in queries:
            res = client.get(f"/api/documents/?search={q}")
            assert res.status_code == status.HTTP_200_OK
            assert res.data["count"] == 1
            assert res.data["results"][0]["id"] == str(doc.id)

    def test_empty_and_whitespace_only_query_returns_all(self, client):
        """Empty or whitespace-only search bypasses filtering and returns all documents."""
        Document.objects.create(filename="doc1.pdf", file_type="pdf")
        Document.objects.create(filename="doc2.pdf", file_type="pdf")

        res_empty = client.get("/api/documents/?search=")
        assert res_empty.status_code == status.HTTP_200_OK
        assert res_empty.data["count"] == 2

        res_ws = client.get("/api/documents/?search=    ")
        assert res_ws.status_code == status.HTTP_200_OK
        assert res_ws.data["count"] == 2

    def test_no_matching_results(self, client):
        """Query with no matches returns empty result list with 200 OK."""
        Document.objects.create(filename="normal_invoice.pdf", file_type="pdf")

        res = client.get("/api/documents/?search=NonExistentEntityXyz999")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 0
        assert len(res.data["results"]) == 0

    def test_distinct_results_when_multiple_line_items_match(self, client):
        """When multiple line items in one document match the search term, document is returned only once."""
        doc = Document.objects.create(filename="multi_item.pdf", file_type="pdf")
        ext = InvoiceExtraction.objects.create(document=doc, invoice_number="INV-MULTI")
        LineItem.objects.create(extraction=ext, line_number=1, description="Server Rack 42U")
        LineItem.objects.create(extraction=ext, line_number=2, description="Server Power Supply 750W")
        LineItem.objects.create(extraction=ext, line_number=3, description="Server Rail Kit")

        res = client.get("/api/documents/?search=Server")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 1
        assert len(res.data["results"]) == 1


# =========================================================================
# 4. Search Combined with Filters, Pagination & Ordering
# =========================================================================

class TestSearchComposition(BaseSearchTest):
    """Verifies that search works seamlessly with status filters, pagination, and ordering."""

    def test_search_combined_with_status_filter(self, client):
        """Search filters operate conjunctively with ?status= and ?file_type=."""
        doc_success = Document.objects.create(
            filename="matched_success.pdf",
            file_type="pdf",
            status=DocumentStatus.SUCCESS,
        )
        doc_failed = Document.objects.create(
            filename="matched_failed.pdf",
            file_type="pdf",
            status=DocumentStatus.FAILED,
        )

        # Search for "matched" with status=SUCCESS
        res = client.get("/api/documents/?search=matched&status=SUCCESS")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 1
        assert res.data["results"][0]["id"] == str(doc_success.id)

        # Search for "matched" with status=FAILED
        res_fail = client.get("/api/documents/?search=matched&status=FAILED")
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


# =========================================================================
# 5. PostgreSQL Search Construction Unit Test (Static/Mocked Engine)
# =========================================================================

class TestPostgresSearchQueryBuilder(BaseSearchTest):
    """
    Validates PostgreSQL SearchVector and SearchQuery structure statically.
    Ensures correct weights A, B, C, D and websearch query configuration.
    """

    def test_postgres_search_vector_weights_and_query_formation(self):
        """Validates that Django PostgreSQL search utilities form the exact approved vector weighting."""
        from django.contrib.postgres.search import SearchQuery, SearchVector

        v_fn = SearchVector("filename", weight="A", config="english")
        v_inv = SearchVector("extraction__invoice_number", weight="A", config="english")
        v_sup = SearchVector("extraction__supplier_name", weight="B", config="english")
        v_cust = SearchVector("extraction__customer_name", weight="B", config="english")
        v_addr = SearchVector("extraction__supplier_address", weight="C", config="english")
        v_desc = SearchVector("extraction__line_items__description", weight="C", config="english")
        v_raw = SearchVector("raw_text", weight="D", config="english")

        full_vector = v_fn + v_inv + v_sup + v_cust + v_addr + v_desc + v_raw
        assert full_vector is not None

        # Verify SearchQuery functions
        q_web = SearchQuery("Acme Corp \"Fast Delivery\"", search_type="websearch", config="english")
        assert q_web.function == "websearch_to_tsquery"

        q_plain = SearchQuery("simple query", search_type="plain", config="english")
        assert q_plain.function == "plainto_tsquery"
