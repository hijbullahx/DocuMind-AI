"""
PostgreSQL Full-Text Search and Multi-Field Fallback Engine for DocuMind-AI.

Implements:
1. Native PostgreSQL Full-Text Search using Django PostgreSQL search utilities:
   - SearchVector, SearchQuery, and SearchRank.
   - 4-tier weighting hierarchy:
     * Weight A (Highest): Document.filename, InvoiceExtraction.invoice_number
     * Weight B (Primary Entities): InvoiceExtraction.supplier_name, InvoiceExtraction.customer_name
     * Weight C (Secondary Details): InvoiceExtraction.supplier_address, InvoiceExtraction.customer_address, LineItem.description
     * Weight D (Document Body): Document.raw_text
   - Multi-word and phrase parsing using websearch syntax with graceful fallback to plain search.
   - Search ranking annotation and relevance ordering.
2. Robust SQLite / Development Fallback:
   - Multi-field Q-lookup matching across all A, B, C, and D tiers.
   - Word tokenization for multi-word queries (AND logic across distinct tokens).
   - Exact phrase and token-level matching.
   - Safe parameterization against special characters, wildcards, and punctuation.
3. Query Lifecycle Guards:
   - Bypasses search logic entirely for empty or whitespace-only queries.
   - Preserves existing filters, pagination, and custom orderings.
"""
import logging
import re
from typing import List, Optional

from django.db import connection
from django.db.models import Q, QuerySet

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
    Executes native PostgreSQL Full-Text Search with 4-tier weighted ranking:
    - Weight A: Document.filename, InvoiceExtraction.invoice_number
    - Weight B: InvoiceExtraction.supplier_name, InvoiceExtraction.customer_name
    - Weight C: InvoiceExtraction.supplier_address, InvoiceExtraction.customer_address, LineItem.description
    - Weight D: Document.raw_text

    Uses websearch query syntax with graceful fallback to plain search.
    Annotates search_rank and orders by relevance unless explicit custom ordering is provided.
    """
    from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector

    # 1. Assemble weighted SearchVector
    vector = (
        SearchVector("filename", weight="A", config="english")
        + SearchVector("extraction__invoice_number", weight="A", config="english")
        + SearchVector("extraction__supplier_name", weight="B", config="english")
        + SearchVector("extraction__customer_name", weight="B", config="english")
        + SearchVector("extraction__supplier_address", weight="C", config="english")
        + SearchVector("extraction__customer_address", weight="C", config="english")
        + SearchVector("extraction__line_items__description", weight="C", config="english")
        + SearchVector("raw_text", weight="D", config="english")
    )

    # 2. Build SearchQuery using websearch (supports quotes, boolean OR, negation)
    try:
        query_obj = SearchQuery(clean_query, search_type="websearch", config="english")
    except Exception as exc:
        logger.debug(f"[Search] websearch syntax failed for '{clean_query}': {exc}; falling back to plain.")
        query_obj = SearchQuery(clean_query, search_type="plain", config="english")

    # 3. Annotate rank and filter by relevance
    ranked_qs = (
        queryset
        .annotate(search_rank=SearchRank(vector, query_obj))
        .filter(search_rank__gt=0.0)
        .distinct()
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
    - On PostgreSQL: executes weighted Full-Text Search with ranking.
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
