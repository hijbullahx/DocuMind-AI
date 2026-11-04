"""
Deterministic Cross-Document Verification Engine for DocuMind-AI.
Compares extracted records across paired business documents (PDF-PDF, PDF-Excel, Invoice-PO, Invoice-Ledger)
and detects meaningful discrepancies across totals, subtotals, tax, currencies, parties, references,
and itemized products/services.
"""
from decimal import Decimal
from enum import Enum
import re
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from pydantic import BaseModel, Field

from apps.extraction.schemas import ExtractionSchemaError, InvoiceExtraction, LineItemExtraction
from apps.ingestion.base import DocumentExtractionResult
from .models import ValidationSeverity, ValidationStatus

DEFAULT_TOLERANCE: Decimal = Decimal("0.05")

# Common stop words for token-overlap matching of item descriptions
_STOPWORDS: Set[str] = {
    "a", "an", "the", "and", "or", "of", "for", "with", "to", "in", "on", "at",
    "by", "item", "part", "unit", "pcs", "ea", "each", "box", "set", "no", "num",
}

# Standard currency mapping
_CURRENCY_MAP: Dict[str, str] = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "₹": "INR",
}


class CrossVerificationRuleId(str, Enum):
    """Rule identifiers for cross-document reconciliation checks."""
    CROSS_TOTAL_MISMATCH = "CROSS_TOTAL_MISMATCH"
    CROSS_SUBTOTAL_MISMATCH = "CROSS_SUBTOTAL_MISMATCH"
    CROSS_TAX_MISMATCH = "CROSS_TAX_MISMATCH"
    CROSS_CURRENCY_MISMATCH = "CROSS_CURRENCY_MISMATCH"
    CROSS_SUPPLIER_MISMATCH = "CROSS_SUPPLIER_MISMATCH"
    CROSS_CUSTOMER_MISMATCH = "CROSS_CUSTOMER_MISMATCH"
    CROSS_REFERENCE_MISMATCH = "CROSS_REFERENCE_MISMATCH"
    CROSS_ITEM_MISMATCH = "CROSS_ITEM_MISMATCH"
    CROSS_UNMATCHED_ITEM = "CROSS_UNMATCHED_ITEM"
    CROSS_INCOMPLETE_COMPARISON = "CROSS_INCOMPLETE_COMPARISON"
    CROSS_INCOMPATIBLE_DOCUMENT = "CROSS_INCOMPATIBLE_DOCUMENT"


class CrossDocumentDiscrepancy(BaseModel):
    """
    Actionable discrepancy identified between paired documents.
    Captures the specific rule, field, document IDs, conflicting values, and difference.
    """
    rule_id: str = Field(..., description="Cross-verification rule identifier string or CrossVerificationRuleId")
    field: str = Field(..., description="Target field name or path (e.g. 'total', 'line_items[0].quantity')")
    message: str = Field(..., description="Human-readable explanation of the discrepancy")
    severity: ValidationSeverity = Field(
        default=ValidationSeverity.ERROR,
        description="Severity level: ERROR (reconciliation failed), WARNING (review required)"
    )
    doc_a_value: Optional[str] = Field(None, description="Value extracted from Document A")
    doc_b_value: Optional[str] = Field(None, description="Value extracted from Document B")
    doc_a_id: str = Field(default="doc_a", description="Identifier or filename of Document A")
    doc_b_id: str = Field(default="doc_b", description="Identifier or filename of Document B")
    difference: Optional[Decimal] = Field(None, description="Arithmetic difference if numerical")

    def to_dict(self) -> Dict[str, Any]:
        """Serializes discrepancy to dictionary representation."""
        return {
            "rule_id": str(self.rule_id),
            "field": self.field,
            "message": self.message,
            "severity": self.severity.value,
            "doc_a_value": self.doc_a_value,
            "doc_b_value": self.doc_b_value,
            "doc_a_id": self.doc_a_id,
            "doc_b_id": self.doc_b_id,
            "difference": str(self.difference) if self.difference is not None else None,
        }


class CrossVerificationResult(BaseModel):
    """
    Consolidated outcome of cross-document reconciliation between two documents.
    """
    status: ValidationStatus = Field(..., description="Overall reconciliation status: VERIFIED, NEEDS_REVIEW, FAILED")
    is_reconciled: bool = Field(..., description="True if status is VERIFIED (no discrepancies or review warnings)")
    doc_a_id: str = Field(default="doc_a", description="Identifier of Document A")
    doc_b_id: str = Field(default="doc_b", description="Identifier of Document B")
    discrepancies: List[CrossDocumentDiscrepancy] = Field(
        default_factory=list,
        description="Critical errors that fail reconciliation"
    )
    warnings: List[CrossDocumentDiscrepancy] = Field(
        default_factory=list,
        description="Non-critical warnings requiring review"
    )
    fields_compared: List[str] = Field(
        default_factory=list,
        description="List of fields that were compared between documents"
    )
    matched_items_count: int = Field(default=0, description="Count of line items successfully matched")
    unmatched_items_count: int = Field(default=0, description="Count of unmatched line items across both documents")
    summary: str = Field(default="", description="Human-readable summary of cross-verification results")

    def to_dict(self) -> Dict[str, Any]:
        """Serializes result to dictionary representation."""
        return {
            "status": self.status.value,
            "is_reconciled": self.is_reconciled,
            "doc_a_id": self.doc_a_id,
            "doc_b_id": self.doc_b_id,
            "discrepancies": [d.to_dict() for d in self.discrepancies],
            "warnings": [w.to_dict() for w in self.warnings],
            "fields_compared": self.fields_compared,
            "matched_items_count": self.matched_items_count,
            "unmatched_items_count": self.unmatched_items_count,
            "summary": self.summary,
        }


def _coerce_tolerance(tolerance: Union[Decimal, float, str, int]) -> Decimal:
    """Converts tolerance safely to Decimal."""
    if isinstance(tolerance, Decimal):
        return tolerance
    return Decimal(str(tolerance))


def _normalize_currency(currency_str: Optional[str]) -> Optional[str]:
    """Normalizes currency codes and symbols (e.g. '$' -> 'USD')."""
    if not currency_str or not str(currency_str).strip():
        return None
    cleaned = str(currency_str).strip().upper()
    return _CURRENCY_MAP.get(cleaned, cleaned)


def _normalize_entity_name(name: Optional[str]) -> str:
    """Normalizes company/supplier/customer names for comparison."""
    if not name or not str(name).strip():
        return ""
    # Strip trailing punctuation, lowercase, collapse internal whitespace
    s = str(name).strip().rstrip(".,;")
    return " ".join(s.split()).lower()


def _tokenize_description(desc: str) -> Set[str]:
    """Extracts non-stopword tokens from item descriptions for similarity comparison."""
    cleaned = re.sub(r"[^\w\s]", " ", desc.lower())
    words = [w for w in cleaned.split() if len(w) >= 2 and w not in _STOPWORDS]
    return set(words)


def _compute_description_similarity(desc_a: str, desc_b: str) -> float:
    """
    Computes a deterministic similarity score in [0.0, 1.0] between two line item descriptions.
    Uses exact normalized equality (1.0) and Jaccard token overlap for minor variations.
    """
    norm_a = " ".join(desc_a.strip().lower().split())
    norm_b = " ".join(desc_b.strip().lower().split())
    if norm_a == norm_b:
        return 1.0

    tokens_a = _tokenize_description(desc_a)
    tokens_b = _tokenize_description(desc_b)

    if not tokens_a or not tokens_b:
        return 0.0

    intersection = tokens_a.intersection(tokens_b)
    union = tokens_a.union(tokens_b)
    return len(intersection) / len(union)


def _extract_from_spreadsheet_tables(doc_result: DocumentExtractionResult) -> InvoiceExtraction:
    """
    Heuristically extracts tabular rows from an ingested spreadsheet or CSV
    DocumentExtractionResult into an InvoiceExtraction model.
    """
    line_items: List[LineItemExtraction] = []
    total_val: Optional[Decimal] = None

    for page in doc_result.pages:
        for table in page.tables:
            if not table or len(table) < 2:
                continue

            headers = [str(col).strip().lower() if col else "" for col in table[0]]
            desc_col = -1
            qty_col = -1
            price_col = -1
            amt_col = -1

            for col_idx, h in enumerate(headers):
                if any(k in h for k in ("desc", "item", "product", "service", "particular")):
                    desc_col = col_idx
                elif any(k in h for k in ("qty", "quantity", "count", "units")):
                    qty_col = col_idx
                elif any(k in h for k in ("unit price", "price", "rate", "cost")):
                    price_col = col_idx
                elif any(k in h for k in ("amount", "total", "line total", "subtotal")) and amt_col == -1:
                    amt_col = col_idx

            if desc_col != -1:
                for row in table[1:]:
                    if desc_col < len(row) and row[desc_col]:
                        raw_desc = str(row[desc_col]).strip()
                        # Skip summary/total rows inside tables
                        if any(k in raw_desc.lower() for k in ("total", "subtotal", "tax", "balance")):
                            continue
                        if not raw_desc or raw_desc.lower() in ("null", "none", "n/a", "-"):
                            continue

                        raw_qty = row[qty_col] if qty_col != -1 and qty_col < len(row) else None
                        raw_price = row[price_col] if price_col != -1 and price_col < len(row) else None
                        raw_amt = row[amt_col] if amt_col != -1 and amt_col < len(row) else None

                        try:
                            item = LineItemExtraction(
                                description=raw_desc,
                                quantity=raw_qty,
                                unit_price=raw_price,
                                amount=raw_amt,
                            )
                            line_items.append(item)
                        except Exception:
                            continue

    computed_sum = sum((item.amount for item in line_items if item.amount is not None), Decimal("0.00"))
    if computed_sum > Decimal("0.00"):
        total_val = computed_sum

    return InvoiceExtraction(
        line_items=line_items,
        subtotal=total_val,
        total=total_val,
    )


class CrossDocumentVerifier:
    """
    Deterministic cross-document verification engine.
    Reconciles two extracted document records (e.g. PDF Invoice vs PDF Purchase Order,
    or PDF Invoice vs Excel Ledger/Spreadsheet).
    """

    def __init__(
        self,
        default_tolerance: Union[Decimal, float, str] = DEFAULT_TOLERANCE,
        strict_reference_matching: bool = False,
        min_item_similarity: float = 0.70,
    ):
        self.default_tolerance = _coerce_tolerance(default_tolerance)
        self.strict_reference_matching = strict_reference_matching
        self.min_item_similarity = min_item_similarity

    def _coerce_input(self, doc_input: Any, doc_name: str) -> Tuple[Optional[InvoiceExtraction], Optional[CrossDocumentDiscrepancy]]:
        """Safely coerces various document inputs into an InvoiceExtraction model."""
        if isinstance(doc_input, InvoiceExtraction):
            return doc_input, None

        if isinstance(doc_input, DocumentExtractionResult):
            try:
                extracted = _extract_from_spreadsheet_tables(doc_input)
                return extracted, None
            except Exception as e:
                err = CrossDocumentDiscrepancy(
                    rule_id=CrossVerificationRuleId.CROSS_INCOMPATIBLE_DOCUMENT.value,
                    field="document",
                    message=f"Failed to parse tabular data from {doc_name}: {e}",
                    severity=ValidationSeverity.ERROR,
                    doc_a_id=doc_name,
                    doc_b_id=doc_name,
                )
                return None, err

        if isinstance(doc_input, list):
            # List of item dicts: [{"description": "...", "amount": 100}]
            try:
                items = [LineItemExtraction.model_validate(it) for it in doc_input]
                computed_total = sum((it.amount for it in items if it.amount is not None), Decimal("0.00"))
                return InvoiceExtraction(
                    line_items=items,
                    subtotal=computed_total if computed_total > 0 else None,
                    total=computed_total if computed_total > 0 else None,
                ), None
            except Exception as e:
                err = CrossDocumentDiscrepancy(
                    rule_id=CrossVerificationRuleId.CROSS_INCOMPATIBLE_DOCUMENT.value,
                    field="line_items",
                    message=f"Failed to parse item list from {doc_name}: {e}",
                    severity=ValidationSeverity.ERROR,
                    doc_a_id=doc_name,
                    doc_b_id=doc_name,
                )
                return None, err

        if isinstance(doc_input, dict):
            try:
                return InvoiceExtraction.model_validate(doc_input), None
            except Exception as e:
                err = CrossDocumentDiscrepancy(
                    rule_id=CrossVerificationRuleId.CROSS_INCOMPATIBLE_DOCUMENT.value,
                    field="document",
                    message=f"Dictionary data in {doc_name} failed InvoiceExtraction schema: {e}",
                    severity=ValidationSeverity.ERROR,
                    doc_a_id=doc_name,
                    doc_b_id=doc_name,
                )
                return None, err

        if isinstance(doc_input, str):
            try:
                return InvoiceExtraction.from_raw_json(doc_input), None
            except ExtractionSchemaError as e:
                err = CrossDocumentDiscrepancy(
                    rule_id=CrossVerificationRuleId.CROSS_INCOMPATIBLE_DOCUMENT.value,
                    field="document",
                    message=f"Raw text in {doc_name} failed JSON/schema parsing: {e}",
                    severity=ValidationSeverity.ERROR,
                    doc_a_id=doc_name,
                    doc_b_id=doc_name,
                )
                return None, err

        err = CrossDocumentDiscrepancy(
            rule_id=CrossVerificationRuleId.CROSS_INCOMPATIBLE_DOCUMENT.value,
            field="document",
            message=f"Unsupported input document type in {doc_name}: {type(doc_input).__name__}",
            severity=ValidationSeverity.ERROR,
            doc_a_id=doc_name,
            doc_b_id=doc_name,
        )
        return None, err

    def reconcile(
        self,
        doc_a: Any,
        doc_b: Any,
        doc_a_id: str = "doc_a",
        doc_b_id: str = "doc_b",
        tolerance: Optional[Union[Decimal, float, str]] = None,
        strict_reference_matching: Optional[bool] = None,
    ) -> CrossVerificationResult:
        """
        Reconciles two documents and returns a structured CrossVerificationResult.

        Args:
            doc_a: Primary document (InvoiceExtraction, dict, JSON str, or spreadsheet result).
            doc_b: Comparison document (InvoiceExtraction, dict, JSON str, or spreadsheet result).
            doc_a_id: Label / identifier for Document A.
            doc_b_id: Label / identifier for Document B.
            tolerance: Custom arithmetic discrepancy threshold (default 0.05).
            strict_reference_matching: True if reference/invoice numbers must match identically (ERROR if different).
        """
        tol = _coerce_tolerance(tolerance) if tolerance is not None else self.default_tolerance
        strict_ref = strict_reference_matching if strict_reference_matching is not None else self.strict_reference_matching

        fields_compared: List[str] = []
        discrepancies: List[CrossDocumentDiscrepancy] = []
        warnings: List[CrossDocumentDiscrepancy] = []
        reported_keys: Set[str] = set()

        def _add_issue(issue: CrossDocumentDiscrepancy) -> None:
            """Prevents duplicate discrepancy reports for the same underlying field issue."""
            dedup_key = f"{issue.rule_id}:{issue.field}:{issue.doc_a_value}:{issue.doc_b_value}"
            if dedup_key in reported_keys:
                return
            reported_keys.add(dedup_key)
            if issue.severity == ValidationSeverity.ERROR:
                discrepancies.append(issue)
            else:
                warnings.append(issue)

        # 1. Coerce input documents
        model_a, err_a = self._coerce_input(doc_a, doc_a_id)
        if err_a:
            _add_issue(err_a)
            return CrossVerificationResult(
                status=ValidationStatus.FAILED,
                is_reconciled=False,
                doc_a_id=doc_a_id,
                doc_b_id=doc_b_id,
                discrepancies=discrepancies,
                warnings=[],
                fields_compared=["document"],
                summary=f"Reconciliation aborted: {err_a.message}",
            )

        model_b, err_b = self._coerce_input(doc_b, doc_b_id)
        if err_b:
            _add_issue(err_b)
            return CrossVerificationResult(
                status=ValidationStatus.FAILED,
                is_reconciled=False,
                doc_a_id=doc_a_id,
                doc_b_id=doc_b_id,
                discrepancies=discrepancies,
                warnings=[],
                fields_compared=["document"],
                summary=f"Reconciliation aborted: {err_b.message}",
            )

        assert model_a is not None and model_b is not None

        # 2. Total Amount Comparison
        fields_compared.append("total")
        if model_a.total is not None and model_b.total is not None:
            diff = abs(model_a.total - model_b.total)
            if diff > tol:
                _add_issue(
                    CrossDocumentDiscrepancy(
                        rule_id=CrossVerificationRuleId.CROSS_TOTAL_MISMATCH.value,
                        field="total",
                        message=(
                            f"Total amount mismatch between {doc_a_id} ({model_a.total}) and {doc_b_id} ({model_b.total}) "
                            f"(difference: {diff}, tolerance: {tol})."
                        ),
                        severity=ValidationSeverity.ERROR,
                        doc_a_value=str(model_a.total),
                        doc_b_value=str(model_b.total),
                        doc_a_id=doc_a_id,
                        doc_b_id=doc_b_id,
                        difference=diff,
                    )
                )
        else:
            # Conservative rule: missing total is not treated as a mismatch
            _add_issue(
                CrossDocumentDiscrepancy(
                    rule_id=CrossVerificationRuleId.CROSS_INCOMPLETE_COMPARISON.value,
                    field="total",
                    message=(
                        f"Total amount is missing in one or both documents ({doc_a_id}: {model_a.total}, {doc_b_id}: {model_b.total}); "
                        "total reconciliation could not be completed."
                    ),
                    severity=ValidationSeverity.WARNING,
                    doc_a_value=str(model_a.total) if model_a.total is not None else None,
                    doc_b_value=str(model_b.total) if model_b.total is not None else None,
                    doc_a_id=doc_a_id,
                    doc_b_id=doc_b_id,
                )
            )

        # 3. Subtotal Amount Comparison
        fields_compared.append("subtotal")
        if model_a.subtotal is not None and model_b.subtotal is not None:
            diff = abs(model_a.subtotal - model_b.subtotal)
            if diff > tol:
                _add_issue(
                    CrossDocumentDiscrepancy(
                        rule_id=CrossVerificationRuleId.CROSS_SUBTOTAL_MISMATCH.value,
                        field="subtotal",
                        message=(
                            f"Subtotal mismatch between {doc_a_id} ({model_a.subtotal}) and {doc_b_id} ({model_b.subtotal}) "
                            f"(difference: {diff}, tolerance: {tol})."
                        ),
                        severity=ValidationSeverity.ERROR,
                        doc_a_value=str(model_a.subtotal),
                        doc_b_value=str(model_b.subtotal),
                        doc_a_id=doc_a_id,
                        doc_b_id=doc_b_id,
                        difference=diff,
                    )
                )

        # 4. Tax Amount Comparison
        fields_compared.append("tax")
        if model_a.tax is not None and model_b.tax is not None:
            diff = abs(model_a.tax - model_b.tax)
            if diff > tol:
                _add_issue(
                    CrossDocumentDiscrepancy(
                        rule_id=CrossVerificationRuleId.CROSS_TAX_MISMATCH.value,
                        field="tax",
                        message=(
                            f"Tax amount mismatch between {doc_a_id} ({model_a.tax}) and {doc_b_id} ({model_b.tax}) "
                            f"(difference: {diff}, tolerance: {tol})."
                        ),
                        severity=ValidationSeverity.ERROR,
                        doc_a_value=str(model_a.tax),
                        doc_b_value=str(model_b.tax),
                        doc_a_id=doc_a_id,
                        doc_b_id=doc_b_id,
                        difference=diff,
                    )
                )

        # 5. Currency Comparison
        fields_compared.append("currency")
        curr_a = _normalize_currency(model_a.currency)
        curr_b = _normalize_currency(model_b.currency)
        if curr_a and curr_b and curr_a != curr_b:
            _add_issue(
                CrossDocumentDiscrepancy(
                    rule_id=CrossVerificationRuleId.CROSS_CURRENCY_MISMATCH.value,
                    field="currency",
                    message=(
                        f"Currency conflict: {doc_a_id} specifies '{model_a.currency}' ({curr_a}), "
                        f"while {doc_b_id} specifies '{model_b.currency}' ({curr_b})."
                    ),
                    severity=ValidationSeverity.ERROR,
                    doc_a_value=model_a.currency,
                    doc_b_value=model_b.currency,
                    doc_a_id=doc_a_id,
                    doc_b_id=doc_b_id,
                )
            )

        # 6. Supplier Legal Entity Comparison
        fields_compared.append("supplier_name")
        supp_a = _normalize_entity_name(model_a.supplier_name)
        supp_b = _normalize_entity_name(model_b.supplier_name)
        if supp_a and supp_b and supp_a != supp_b:
            _add_issue(
                CrossDocumentDiscrepancy(
                    rule_id=CrossVerificationRuleId.CROSS_SUPPLIER_MISMATCH.value,
                    field="supplier_name",
                    message=(
                        f"Supplier legal entity mismatch: {doc_a_id} has '{model_a.supplier_name}', "
                        f"whereas {doc_b_id} has '{model_b.supplier_name}'."
                    ),
                    severity=ValidationSeverity.ERROR,
                    doc_a_value=model_a.supplier_name,
                    doc_b_value=model_b.supplier_name,
                    doc_a_id=doc_a_id,
                    doc_b_id=doc_b_id,
                )
            )

        # 7. Customer Recipient Comparison
        fields_compared.append("customer_name")
        cust_a = _normalize_entity_name(model_a.customer_name)
        cust_b = _normalize_entity_name(model_b.customer_name)
        if cust_a and cust_b and cust_a != cust_b:
            _add_issue(
                CrossDocumentDiscrepancy(
                    rule_id=CrossVerificationRuleId.CROSS_CUSTOMER_MISMATCH.value,
                    field="customer_name",
                    message=(
                        f"Customer recipient mismatch: {doc_a_id} has '{model_a.customer_name}', "
                        f"while {doc_b_id} has '{model_b.customer_name}'."
                    ),
                    severity=ValidationSeverity.WARNING,
                    doc_a_value=model_a.customer_name,
                    doc_b_value=model_b.customer_name,
                    doc_a_id=doc_a_id,
                    doc_b_id=doc_b_id,
                )
            )

        # 8. Document Reference / Invoice Number Comparison
        fields_compared.append("invoice_number")
        if model_a.invoice_number and model_b.invoice_number:
            ref_a = " ".join(str(model_a.invoice_number).strip().split()).lower()
            ref_b = " ".join(str(model_b.invoice_number).strip().split()).lower()
            if ref_a != ref_b:
                sev = ValidationSeverity.ERROR if strict_ref else ValidationSeverity.WARNING
                _add_issue(
                    CrossDocumentDiscrepancy(
                        rule_id=CrossVerificationRuleId.CROSS_REFERENCE_MISMATCH.value,
                        field="invoice_number",
                        message=(
                            f"Document reference discrepancy: {doc_a_id} references '{model_a.invoice_number}', "
                            f"while {doc_b_id} references '{model_b.invoice_number}'."
                        ),
                        severity=sev,
                        doc_a_value=model_a.invoice_number,
                        doc_b_value=model_b.invoice_number,
                        doc_a_id=doc_a_id,
                        doc_b_id=doc_b_id,
                    )
                )

        # 9. Line Item Cross-Reconciliation
        fields_compared.append("line_items")
        items_a = model_a.line_items
        items_b = model_b.line_items

        # Build candidate matches with similarity >= min_item_similarity
        candidate_pairs: List[Tuple[float, int, int, int]] = []
        for idx_a, it_a in enumerate(items_a):
            for idx_b, it_b in enumerate(items_b):
                sim = _compute_description_similarity(it_a.description, it_b.description)
                if sim >= self.min_item_similarity:
                    amt_match = 1 if (
                        it_a.amount is not None
                        and it_b.amount is not None
                        and abs(it_a.amount - it_b.amount) <= tol
                    ) else 0
                    candidate_pairs.append((sim, amt_match, idx_a, idx_b))

        # Sort candidates globally:
        # 1. Higher similarity first (-sim)
        # 2. Matching financial amounts first (-amt_match)
        # 3. Deterministic order by indices (idx_a, idx_b)
        candidate_pairs.sort(key=lambda x: (-x[0], -x[1], x[2], x[3]))

        matched_a_indices: Set[int] = set()
        matched_b_indices: Set[int] = set()
        matched_pairs: List[Tuple[int, int]] = []

        for sim, amt_match, idx_a, idx_b in candidate_pairs:
            if idx_a not in matched_a_indices and idx_b not in matched_b_indices:
                matched_pairs.append((idx_a, idx_b))
                matched_a_indices.add(idx_a)
                matched_b_indices.add(idx_b)

        matched_count = len(matched_pairs)
        unmatched_a_with_idx = [(idx, it) for idx, it in enumerate(items_a) if idx not in matched_a_indices]
        unmatched_b_with_idx = [(idx, it) for idx, it in enumerate(items_b) if idx not in matched_b_indices]
        unmatched_count = len(unmatched_a_with_idx) + len(unmatched_b_with_idx)

        # Check matched item calculations
        for idx_a, idx_b in matched_pairs:
            it_a = items_a[idx_a]
            it_b = items_b[idx_b]
            desc_label = it_a.description

            # Quantity check
            if it_a.quantity is not None and it_b.quantity is not None:
                qty_diff = abs(it_a.quantity - it_b.quantity)
                if qty_diff > Decimal("0.001"):
                    _add_issue(
                        CrossDocumentDiscrepancy(
                            rule_id=CrossVerificationRuleId.CROSS_ITEM_MISMATCH.value,
                            field=f"line_items[{idx_a}].quantity",
                            message=(
                                f"Quantity mismatch for item '{desc_label}': {doc_a_id} has {it_a.quantity}, "
                                f"while {doc_b_id} has {it_b.quantity} (difference: {qty_diff})."
                            ),
                            severity=ValidationSeverity.ERROR,
                            doc_a_value=str(it_a.quantity),
                            doc_b_value=str(it_b.quantity),
                            doc_a_id=doc_a_id,
                            doc_b_id=doc_b_id,
                            difference=qty_diff,
                        )
                    )

            # Unit Price check
            if it_a.unit_price is not None and it_b.unit_price is not None:
                price_diff = abs(it_a.unit_price - it_b.unit_price)
                if price_diff > tol:
                    _add_issue(
                        CrossDocumentDiscrepancy(
                            rule_id=CrossVerificationRuleId.CROSS_ITEM_MISMATCH.value,
                            field=f"line_items[{idx_a}].unit_price",
                            message=(
                                f"Unit price mismatch for item '{desc_label}': {doc_a_id} billed {it_a.unit_price}, "
                                f"while {doc_b_id} has {it_b.unit_price} (difference: {price_diff}, tolerance: {tol})."
                            ),
                            severity=ValidationSeverity.ERROR,
                            doc_a_value=str(it_a.unit_price),
                            doc_b_value=str(it_b.unit_price),
                            doc_a_id=doc_a_id,
                            doc_b_id=doc_b_id,
                            difference=price_diff,
                        )
                    )

            # Total Amount check
            if it_a.amount is not None and it_b.amount is not None:
                amt_diff = abs(it_a.amount - it_b.amount)
                if amt_diff > tol:
                    _add_issue(
                        CrossDocumentDiscrepancy(
                            rule_id=CrossVerificationRuleId.CROSS_ITEM_MISMATCH.value,
                            field=f"line_items[{idx_a}].amount",
                            message=(
                                f"Line amount mismatch for item '{desc_label}': {doc_a_id} has {it_a.amount}, "
                                f"while {doc_b_id} has {it_b.amount} (difference: {amt_diff}, tolerance: {tol})."
                            ),
                            severity=ValidationSeverity.ERROR,
                            doc_a_value=str(it_a.amount),
                            doc_b_value=str(it_b.amount),
                            doc_a_id=doc_a_id,
                            doc_b_id=doc_b_id,
                            difference=amt_diff,
                        )
                    )

        # Flag unmatched items
        for idx_a, it in unmatched_a_with_idx:
            _add_issue(
                CrossDocumentDiscrepancy(
                    rule_id=CrossVerificationRuleId.CROSS_UNMATCHED_ITEM.value,
                    field=f"line_items[{idx_a}]",
                    message=f"Line item [{idx_a}] '{it.description}' is present in {doc_a_id} but missing in {doc_b_id}.",
                    severity=ValidationSeverity.WARNING,
                    doc_a_value=it.description,
                    doc_b_value=None,
                    doc_a_id=doc_a_id,
                    doc_b_id=doc_b_id,
                )
            )

        for idx_b, it in unmatched_b_with_idx:
            _add_issue(
                CrossDocumentDiscrepancy(
                    rule_id=CrossVerificationRuleId.CROSS_UNMATCHED_ITEM.value,
                    field=f"line_items[{idx_b}]",
                    message=f"Line item [{idx_b}] '{it.description}' is present in {doc_b_id} but missing in {doc_a_id}.",
                    severity=ValidationSeverity.WARNING,
                    doc_a_value=None,
                    doc_b_value=it.description,
                    doc_a_id=doc_a_id,
                    doc_b_id=doc_b_id,
                )
            )

        # Deterministic sorting of discrepancies and warnings
        discrepancies.sort(key=lambda d: (d.field, d.rule_id, d.message))
        warnings.sort(key=lambda w: (w.field, w.rule_id, w.message))

        # 10. Status Determination and Summary
        if discrepancies:
            status = ValidationStatus.FAILED
            is_reconciled = False
            summary = (
                f"Cross-document reconciliation failed with {len(discrepancies)} critical discrepancy(ies) "
                f"and {len(warnings)} review warning(s)."
            )
        elif warnings:
            status = ValidationStatus.NEEDS_REVIEW
            is_reconciled = False
            summary = (
                f"Cross-document reconciliation requires review: {len(warnings)} warning(s) flagged "
                f"({matched_count} item(s) matched, {unmatched_count} unmatched)."
            )
        else:
            status = ValidationStatus.VERIFIED
            is_reconciled = True
            summary = (
                f"Cross-document reconciliation successfully verified across all compared fields "
                f"({matched_count} item(s) matched)."
            )

        return CrossVerificationResult(
            status=status,
            is_reconciled=is_reconciled,
            doc_a_id=doc_a_id,
            doc_b_id=doc_b_id,
            discrepancies=discrepancies,
            warnings=warnings,
            fields_compared=fields_compared,
            matched_items_count=matched_count,
            unmatched_items_count=unmatched_count,
            summary=summary,
        )

