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
import html
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from django.db import connection
from django.db.models import Case, F, IntegerField, Q, QuerySet, Value, When

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


def annotate_exact_match_boost(queryset: QuerySet, clean_query: str) -> QuerySet:
    """
    Annotates the queryset with an exact_boost integer score to prioritize exact
    matches over broad partial or OCR body matches:
    - Tier 1 (Score 100): Exact invoice number match
    - Tier 2 (Score 80): Exact filename match
    - Tier 3 (Score 60): Exact supplier or customer match
    - Tier 4 (Score 0): Partial / token match
    """
    if not clean_query:
        return queryset.annotate(exact_boost=Value(0, output_field=IntegerField()))

    return queryset.annotate(
        exact_boost=Case(
            When(extraction__invoice_number__iexact=clean_query, then=Value(100)),
            When(filename__iexact=clean_query, then=Value(80)),
            When(extraction__supplier_name__iexact=clean_query, then=Value(60)),
            When(extraction__customer_name__iexact=clean_query, then=Value(60)),
            default=Value(0),
            output_field=IntegerField(),
        )
    )


def apply_sqlite_fallback_search(
    queryset: QuerySet,
    clean_query: str,
    user_ordering: Optional[str] = None,
) -> QuerySet:
    """
    Applies comprehensive multi-field search for SQLite and non-PostgreSQL backends.
    Supports:
    - Single term matches across any tier.
    - Multi-word queries: combines exact phrase matching with AND logic across all tokens.
    - Safe execution with parameterized icontains lookups.
    - Exact-match boosting for invoice numbers, filenames, and supplier/customer names.
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

    filtered_qs = queryset.filter(combined_q).distinct()
    boosted_qs = annotate_exact_match_boost(filtered_qs, clean_query)

    if not user_ordering or user_ordering == "-created_at":
        return boosted_qs.order_by("-exact_boost", "-created_at")

    return boosted_qs.order_by(user_ordering)


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
    4. Annotates exact-match boost for invoice numbers and filenames.
    5. Orders by exact boost and relevance rank (-exact_boost, -search_rank, -created_at).
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

    # 4. Annotate exact match priority boost
    boosted_qs = annotate_exact_match_boost(ranked_qs, clean_query)

    # 5. Ordering: default to exact boost and relevance rank if no custom ordering is requested
    if not user_ordering or user_ordering == "-created_at":
        return boosted_qs.order_by("-exact_boost", "-search_rank", "-created_at")

    return boosted_qs.order_by(user_ordering)


def apply_document_search(
    queryset: QuerySet,
    search_query: Optional[str],
    user_ordering: Optional[str] = None,
) -> QuerySet:
    """
    Primary search interface for Document listings.
    Inspects active database connection:
    - On PostgreSQL: executes weighted Full-Text Search with ranking using persisted search_vector.
    - On SQLite / other: executes multi-field fallback search with exact-match boost.
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
            return apply_sqlite_fallback_search(queryset, clean_query, user_ordering=user_ordering)
    else:
        return apply_sqlite_fallback_search(queryset, clean_query, user_ordering=user_ordering)


def safe_highlight(text: str, tokens: List[str]) -> str:
    """
    Safely highlights matched search tokens in text.
    First escapes all HTML entities to prevent XSS from OCR or filename content,
    then wraps matched tokens in <mark class="search-highlight">...</mark>.
    """
    if not text:
        return ""
    escaped_text = html.escape(str(text))
    if not tokens:
        return escaped_text

    valid_tokens = [re.escape(html.escape(t.strip())) for t in tokens if len(t.strip()) >= 1]
    if not valid_tokens:
        return escaped_text

    # Sort tokens longest first to ensure greedy matching
    valid_tokens.sort(key=len, reverse=True)
    pattern = re.compile(rf"(?i)({'|'.join(valid_tokens)})")

    return pattern.sub(
        r'<mark class="bg-amber-400/30 text-amber-200 font-semibold px-0.5 rounded">\1</mark>',
        escaped_text,
    )


def generate_search_snippet(doc: Any, clean_query: str, max_chars: int = 180) -> Tuple[str, str, str]:
    """
    Constructs a bounded, safe, highlighted snippet explaining why a document matched.
    Returns: (snippet_html, matched_field_key, matched_field_label)

    Evaluates candidates using phrase match and token overlap scoring:
    - Full phrase matches receive priority boost.
    - Fields matching more tokens beat fields matching fewer tokens.
    - Tie-breaking honors search tier hierarchy:
      Tier A (Invoice, Filename) > Tier B (Supplier, Customer) > Tier C (Line Items) > Tier D (OCR).
    """
    tokens = tokenize_query(clean_query)
    query_lower = clean_query.lower()
    ext = getattr(doc, "extraction", None)

    candidates: List[Tuple[int, str, str, str, str]] = []

    def evaluate_candidate(field_text: Optional[str], field_key: str, field_label: str, prefix: str, tier_prio: int):
        if not field_text:
            return
        fl = str(field_text).lower()
        matched_tokens = sum(1 for t in tokens if t.lower() in fl)
        if not matched_tokens:
            return

        is_phrase_match = query_lower in fl
        score = (1000 if is_phrase_match else 0) + (matched_tokens * 20) + tier_prio
        candidates.append((score, field_text, field_key, field_label, prefix))

    # Tier A (tier_prio 4, 3)
    if ext and ext.invoice_number:
        evaluate_candidate(ext.invoice_number, "INVOICE_NUMBER", "Invoice Reference", "Invoice Reference: ", 4)
    if doc.filename:
        evaluate_candidate(doc.filename, "FILENAME", "Document Filename", "Document Filename: ", 3)

    # Tier B (tier_prio 2)
    if ext and ext.supplier_name:
        evaluate_candidate(ext.supplier_name, "SUPPLIER_NAME", "Supplier / Vendor", "Supplier / Vendor: ", 2)
    if ext and ext.customer_name:
        evaluate_candidate(ext.customer_name, "CUSTOMER_NAME", "Customer / Recipient", "Customer / Recipient: ", 2)

    # Tier C (tier_prio 1)
    if ext:
        for li in ext.line_items.all():
            if li.description:
                evaluate_candidate(li.description, "LINE_ITEM", "Line Item Description", "Line Item: ", 1)

    # Tier D: Raw OCR (tier_prio 0)
    if doc.raw_text:
        evaluate_candidate(doc.raw_text, "OCR_CONTENT", "OCR Document Text", "", 0)

    if candidates:
        # Sort by score descending
        candidates.sort(key=lambda c: c[0], reverse=True)
        best_score, best_text, best_key, best_label, best_prefix = candidates[0]

        # For OCR text or long line items, create bounded window
        if best_key == "OCR_CONTENT" or len(best_text) > max_chars:
            raw = best_text
            raw_lower = raw.lower()
            match_pos = -1

            if query_lower in raw_lower:
                match_pos = raw_lower.find(query_lower)
            else:
                for t in tokens:
                    t_lower = t.lower()
                    pos = raw_lower.find(t_lower)
                    if pos != -1:
                        match_pos = pos
                        break

            if match_pos != -1:
                half = max_chars // 2
                start = max(0, match_pos - half)
                end = min(len(raw), match_pos + half)

                if start > 0:
                    space_before = raw.find(" ", start)
                    if space_before != -1 and space_before < match_pos:
                        start = space_before + 1

                if end < len(raw):
                    space_after = raw.rfind(" ", match_pos, end)
                    if space_after != -1 and space_after > match_pos:
                        end = space_after

                excerpt = raw[start:end].strip()
                if start > 0:
                    excerpt = "..." + excerpt
                if end < len(raw):
                    excerpt = excerpt + "..."
                return (safe_highlight(excerpt, tokens), best_key, best_label)

        # Standard header or short field
        formatted = f"{best_prefix}{safe_highlight(best_text, tokens)}" if best_prefix else safe_highlight(best_text, tokens)
        return (formatted, best_key, best_label)

    # Fallback metadata
    info_parts = [doc.filename]
    if ext and ext.supplier_name:
        info_parts.append(ext.supplier_name)
    if ext and ext.invoice_number:
        info_parts.append(f"#{ext.invoice_number}")
    fallback_text = " • ".join(info_parts)
    return (
        safe_highlight(fallback_text, tokens),
        "METADATA",
        "Document Metadata",
    )


def search_documents_service(
    search_query: Optional[str] = None,
    status_filter: Optional[str] = None,
    validation_status_filter: Optional[str] = None,
    file_type_filter: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    supplier_filter: Optional[str] = None,
    customer_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
) -> Dict[str, Any]:
    """
    Dedicated search service coordinating multi-tier search, exact-match boost,
    structured filters, pagination, and safe snippet generation.
    """
    from apps.documents.models import Document, ValidationStatusChoices

    clean_query = sanitize_search_query(search_query)
    # Bound query length for protection
    if len(clean_query) > 250:
        clean_query = clean_query[:250].strip()

    qs = Document.objects.all().select_related("extraction").prefetch_related("extraction__line_items")

    # Apply filters
    if status_filter:
        qs = qs.filter(status=status_filter.strip().upper())

    if validation_status_filter:
        val_upper = validation_status_filter.strip().upper()
        if val_upper in ValidationStatusChoices.values:
            qs = qs.filter(validation_status=val_upper)

    if file_type_filter:
        qs = qs.filter(file_type__iexact=file_type_filter.strip())

    if date_from:
        try:
            qs = qs.filter(created_at__date__gte=date_from.strip())
        except (ValueError, TypeError):
            pass

    if date_to:
        try:
            qs = qs.filter(created_at__date__lte=date_to.strip())
        except (ValueError, TypeError):
            pass

    if supplier_filter:
        qs = qs.filter(extraction__supplier_name__icontains=supplier_filter.strip())

    if customer_filter:
        qs = qs.filter(extraction__customer_name__icontains=customer_filter.strip())

    # Empty query check: if no query and no filters, return empty set
    has_active_filters = bool(
        status_filter
        or validation_status_filter
        or file_type_filter
        or date_from
        or date_to
        or supplier_filter
        or customer_filter
    )
    if not clean_query and not has_active_filters:
        return {
            "query": "",
            "count": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
            "results": [],
        }

    # Apply search if query present
    if clean_query:
        qs = apply_document_search(qs, clean_query)
    else:
        qs = qs.order_by("-created_at")

    total_count = qs.count()
    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0

    # Bounds on page and page_size
    page = max(1, page)
    page_size = min(50, max(1, page_size))
    offset = (page - 1) * page_size
    page_docs = list(qs[offset : offset + page_size])

    results = []
    for doc in page_docs:
        snippet, matched_field, matched_label = generate_search_snippet(doc, clean_query)
        ext = getattr(doc, "extraction", None)
        results.append({
            "id": str(doc.id),
            "filename": doc.filename,
            "status": doc.status,
            "validation_status": doc.validation_status,
            "file_type": doc.file_type,
            "file_size_bytes": doc.file_size_bytes,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "invoice_number": ext.invoice_number if ext else None,
            "invoice_date": ext.invoice_date.isoformat() if ext and ext.invoice_date else None,
            "supplier_name": ext.supplier_name if ext else None,
            "customer_name": ext.customer_name if ext else None,
            "total": str(ext.total) if ext and ext.total is not None else None,
            "currency": ext.currency if ext else None,
            "snippet": snippet,
            "matched_field": matched_field,
            "matched_field_label": matched_label,
            "search_rank": float(getattr(doc, "search_rank", 0.0)) if hasattr(doc, "search_rank") else None,
        })

    return {
        "query": clean_query,
        "count": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "results": results,
    }

