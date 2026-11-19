"""
PostgreSQL Full-Text Search and Multi-Field Fallback Engine for DocuMind-AI.

Implements:
1. Native PostgreSQL Full-Text Search using Persisted SearchVector:
   - Persisted SearchVectorField on Document (Document.search_vector).
   - 4-tier weighting hierarchy:
     * Weight A (Highest): Document.filename, InvoiceExtraction.invoice_number
     * Weight B (Primary Entities): InvoiceExtraction.supplier_name, InvoiceExtraction.customer_name
     * Weight C (Secondary Details): InvoiceExtraction.supplier_address, InvoiceExtraction.customer_address, LineItem.description
     * Weight D (Document Body): Document.raw_text
   - GIN-indexable full-text matching condition: Document.objects.filter(search_vector=query_obj).
     Compiles directly to native PostgreSQL @@ operator utilizing doc_search_vector_gin index via Bitmap Index Scan.
   - Zero joins to LineItem or InvoiceExtraction at query time, completely eliminating Cartesian duplicates.
   - Relevance ranking via SearchRank(F("search_vector"), query_obj) and -search_rank ordering.
   - Websearch query parsing with graceful fallback to plain search.
2. Robust SQLite / Development Fallback:
   - Multi-field Q-lookup matching across all A, B, C, and D tiers.
   - Word tokenization for multi-word queries (AND logic across distinct tokens).
   - Exact phrase and token-level matching.
   - Safe parameterization against special characters, wildcards, and punctuation.
3. Search Vector Synchronization Lifecycle:
   - build_document_search_vector_parts: extracts data for tiers A, B, C, D across Document, Extraction, LineItems.
   - update_document_search_vector: compiles and updates Document.search_vector.
   - Triggered via Django signals (post_save, post_delete) on Document, InvoiceExtraction, and LineItem.
4. Query Lifecycle Guards:
   - Bypasses search logic entirely for empty or whitespace-only queries.
   - Preserves existing filters, pagination, and custom orderings.
"""
import logging
import re
from typing import Any, Dict, List, Optional

from django.db import connection
from django.db.models import F, Q, QuerySet

logger = logging.getLogger(__name__)


def sanitize_search_query(raw_query: Optional[str]) -> str:
    """
    Strips leading/trailing whitespace and normalizes internal whitespace.
    Returns empty string if query is empty or whitespace-only.
    """
    if not raw_query:
        return ""
    # Normalize consecutive whitespace characters to a single space
    cleaned = re.sub(r"\s+", " ", str(raw_query).strip())
    return cleaned


def tokenize_query(clean_query: str) -> List[str]:
    """
    Extracts individual search tokens from a multi-word query string.
    Filters out empty strings while preserving alphanumeric and special symbol tokens.
    """
    if not clean_query:
        return []
    return [t for t in clean_query.split(" ") if t]


def build_document_search_vector_parts(document_id: Any) -> Optional[Dict[str, List[str]]]:
    """
    Extracts and organizes text tokens into the 4 weighted search tiers
    for a given document across Document, InvoiceExtraction, and LineItem records.

    Tiers:
    - Weight A: filename, invoice_number
    - Weight B: supplier_name, customer_name
    - Weight C: supplier_address, customer_address, line_items.description
    - Weight D: raw_text

    Returns a dict with keys 'A', 'B', 'C', 'D' containing lists of non-empty strings,
    or None if the document does not exist.
    """
    from apps.documents.models import Document, InvoiceExtraction, LineItem

    try:
        doc = Document.objects.filter(id=document_id).first()
        if not doc:
            return None

        extraction = InvoiceExtraction.objects.filter(document_id=document_id).first()

        tier_a: List[str] = []
        tier_b: List[str] = []
        tier_c: List[str] = []
        tier_d: List[str] = []

        # Tier A: Document.filename, InvoiceExtraction.invoice_number
        if doc.filename:
            tier_a.append(doc.filename.strip())
        if extraction and extraction.invoice_number:
            tier_a.append(extraction.invoice_number.strip())

        # Tier B: InvoiceExtraction.supplier_name, InvoiceExtraction.customer_name
        if extraction:
            if extraction.supplier_name:
                tier_b.append(extraction.supplier_name.strip())
            if extraction.customer_name:
                tier_b.append(extraction.customer_name.strip())

        # Tier C: InvoiceExtraction.supplier_address, InvoiceExtraction.customer_address, LineItem.description
        if extraction:
            if extraction.supplier_address:
                tier_c.append(extraction.supplier_address.strip())
            if extraction.customer_address:
                tier_c.append(extraction.customer_address.strip())

            line_descriptions = list(
                LineItem.objects.filter(extraction=extraction)
                .values_list("description", flat=True)
            )
            for desc in line_descriptions:
                if desc and desc.strip():
                    tier_c.append(desc.strip())

        # Tier D: Document.raw_text
        if doc.raw_text:
            tier_d.append(doc.raw_text.strip())

        return {
            "A": [t for t in tier_a if t],
            "B": [t for t in tier_b if t],
            "C": [t for t in tier_c if t],
            "D": [t for t in tier_d if t],
        }
    except Exception as exc:
        logger.error(f"[Search] Failed to extract search vector parts for document {document_id}: {exc}")
        return None


def update_document_search_vector(document_id: Any) -> bool:
    """
    Compiles and synchronizes the persisted search_vector on Document.
    Compiles weighted SearchVector expressions across tiers A, B, C, D
    and executes an atomic UPDATE on Document.search_vector.

    On PostgreSQL:
    - Compiles setweight(to_tsvector(...), 'A') || setweight(...) expressions.
    - Updates documents_document.search_vector directly.
    - PostgreSQL automatically synchronizes doc_search_vector_gin index.

    On SQLite / non-PostgreSQL:
    - Gracefully completes without error (SQLite uses multi-field fallback search).

    Returns True if update succeeded or gracefully handled, False if document missing.
    """
    from apps.documents.models import Document

    parts = build_document_search_vector_parts(document_id)
    if parts is None:
        return False

    if connection.vendor == "postgresql":
        try:
            from django.contrib.postgres.search import SearchVector
            from django.db.models import Value

            vector = None
            if parts["A"]:
                vec_a = SearchVector(Value(" ".join(parts["A"])), weight="A", config="english")
                vector = vec_a if vector is None else vector + vec_a
            if parts["B"]:
                vec_b = SearchVector(Value(" ".join(parts["B"])), weight="B", config="english")
                vector = vec_b if vector is None else vector + vec_b
            if parts["C"]:
                vec_c = SearchVector(Value(" ".join(parts["C"])), weight="C", config="english")
                vector = vec_c if vector is None else vector + vec_c
            if parts["D"]:
                vec_d = SearchVector(Value(" ".join(parts["D"])), weight="D", config="english")
                vector = vec_d if vector is None else vector + vec_d

            Document.objects.filter(id=document_id).update(search_vector=vector)
            return True
        except Exception as exc:
            logger.error(f"[Search] PostgreSQL search vector update failed for document {document_id}: {exc}")
            return False

    return True


def _build_sqlite_field_q(term: str) -> Q:
    """
    Constructs an OR Q-expression matching a single search term across all 4 tiers:
    - Weight A: filename, invoice_number
    - Weight B: supplier_name, customer_name
    - Weight C: supplier_address, customer_address, line_items.description
    - Weight D: raw_text
    """
    return (
        Q(filename__icontains=term)
        | Q(extraction__invoice_number__icontains=term)
        | Q(extraction__supplier_name__icontains=term)
        | Q(extraction__customer_name__icontains=term)
        | Q(extraction__supplier_address__icontains=term)
        | Q(extraction__customer_address__icontains=term)
        | Q(extraction__line_items__description__icontains=term)
        | Q(raw_text__icontains=term)
    )


def apply_sqlite_fallback_search(queryset: QuerySet, clean_query: str) -> QuerySet:
    """
    Applies comprehensive multi-field search for SQLite and non-PostgreSQL backends.
    Supports:
    - Single term matches across any tier.
    - Multi-word queries: combines exact phrase matching with AND logic across all tokens.
    - Safe execution with parameterized icontains lookups.
    """
    tokens = tokenize_query(clean_query)
    if not tokens:
        return queryset

    # 1. Exact full phrase match across any searchable field
    phrase_q = _build_sqlite_field_q(clean_query)

    # 2. Multi-token match: each individual word must match somewhere in the document hierarchy
    if len(tokens) > 1:
        token_and_q = Q()
        for token in tokens:
            token_and_q &= _build_sqlite_field_q(token)
        combined_q = phrase_q | token_and_q
    else:
        combined_q = phrase_q

    return queryset.filter(combined_q).distinct()


def apply_postgres_fts(
    queryset: QuerySet,
    clean_query: str,
    user_ordering: Optional[str] = None,
) -> QuerySet:
    """
    Executes native PostgreSQL Full-Text Search against persisted Document.search_vector.

    Architecture:
    1. Compiles SearchQuery using websearch syntax (supports quotes, boolean OR, negation)
       with graceful fallback to plain search.
    2. Filters matching documents via Document.objects.filter(search_vector=query_obj).
       This generates 'documents_document.search_vector @@ to_tsquery(...)' which executes
       a native PostgreSQL Bitmap Index Scan on doc_search_vector_gin.
    3. Annotates relevance score using SearchRank(F("search_vector"), query_obj).
       Because the search vector is stored on Document, zero joins to LineItem or
       InvoiceExtraction are made during query execution, guaranteeing zero duplicate documents.
    4. Orders by relevance rank (-search_rank, -created_at) by default, or user-selected ordering.
    """
    from django.contrib.postgres.search import SearchQuery, SearchRank

    # 1. Build SearchQuery using websearch
    try:
        query_obj = SearchQuery(clean_query, search_type="websearch", config="english")
    except Exception as exc:
        logger.debug(f"[Search] websearch syntax failed for '{clean_query}': {exc}; falling back to plain.")
        query_obj = SearchQuery(clean_query, search_type="plain", config="english")

    # 2. Filter using GIN-indexable @@ condition on persisted search_vector
    matching_qs = queryset.filter(search_vector=query_obj)

    # 3. Annotate rank on matching documents only, without joining LineItem
    ranked_qs = matching_qs.annotate(
        search_rank=SearchRank(F("search_vector"), query_obj)
    )

    # 4. Ordering: default to relevance rank if no custom ordering is requested
    if not user_ordering or user_ordering == "-created_at":
        return ranked_qs.order_by("-search_rank", "-created_at")

    return ranked_qs.order_by(user_ordering)


def apply_document_search(
    queryset: QuerySet,
    search_query: Optional[str],
    user_ordering: Optional[str] = None,
) -> QuerySet:
    """
    Primary search interface for Document listings.
    Inspects active database connection:
    - On PostgreSQL: executes weighted Full-Text Search with ranking using persisted search_vector.
    - On SQLite / other: executes multi-field fallback search.
    Bypasses search logic entirely if query is blank or whitespace-only.
    """
    clean_query = sanitize_search_query(search_query)
    if not clean_query:
        return queryset

    if connection.vendor == "postgresql":
        try:
            return apply_postgres_fts(queryset, clean_query, user_ordering=user_ordering)
        except Exception as exc:
            logger.error(f"[Search] PostgreSQL FTS execution failed: {exc}; falling back to multi-field ORM search.")
            return apply_sqlite_fallback_search(queryset, clean_query)
    else:
        return apply_sqlite_fallback_search(queryset, clean_query)
