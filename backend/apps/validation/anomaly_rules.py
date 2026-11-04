"""
Integrity and Anomaly Validation Rules for DocuMind-AI.
Enforces non-mathematical business integrity:
  1. Missing critical fields (invoice_number, total, invoice_date, supplier_name)
  2. Duplicate invoice detection (supplier_name + invoice_number match)
  3. Unreasonable date values and chronological contradictions (due_date < invoice_date)
  4. Negative financial amount checks
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
import re
from typing import Any, Callable, Iterable, List, Optional, Protocol, Tuple, Union

from dateutil import parser as date_parser

from apps.extraction.schemas import InvoiceExtraction
from .models import ValidationError, ValidationRuleId, ValidationSeverity

CRITICAL_FIELDS = ("invoice_number", "invoice_date", "total")
IMPORTANT_FIELDS = ("supplier_name",)
_NULL_STRINGS = ("null", "none", "n/a", "na", "-", "unknown")


class DuplicateDetectorProtocol(Protocol):
    """Protocol for pluggable duplicate invoice stores."""
    def is_duplicate(self, supplier_name: str, invoice_number: str) -> bool:
        ...


class InMemoryDuplicateDetector:
    """
    In-memory duplicate registry for offline testing and decoupled validation.
    Stores normalized (supplier_name, invoice_number) pairs.

    Normalization Policy:
      - Whitespace normalization: trims leading/trailing whitespace and collapses internal multiple spaces.
      - Case insensitivity: lowercases both supplier name and invoice number.
      - Trailing punctuation stripping on supplier: trims trailing dots/commas (e.g. 'Acme Corp.' -> 'acme corp').
      - Internal punctuation preservation: preserves characters like '&', '#', '-', '/' to prevent
        false duplicate collisions between distinct business entities (e.g. 'C# Tech' vs 'C Tech')
        or distinct invoice numbers (e.g. 'INV-01' vs 'INV/01' or 'A-1' vs 'A1').
    """
    def __init__(self, initial_records: Optional[Iterable[Any]] = None):
        self._registry = set()
        if initial_records:
            for rec in initial_records:
                self.add_record(rec)

    @staticmethod
    def normalize_key(supplier_name: Optional[str], invoice_number: Optional[str]) -> Tuple[str, str]:
        """Normalizes supplier name and invoice number for case/whitespace-insensitive matching."""
        # Trim leading/trailing whitespace, trim trailing entity dots/commas, and collapse internal whitespace
        s_raw = str(supplier_name or "").strip().rstrip(".,;")
        s = " ".join(s_raw.split()).lower()

        # Whitespace-collapsed and lowercased invoice number (preserves internal hyphens, slashes, and symbols)
        inv = " ".join(str(invoice_number or "").strip().split()).lower()
        return s, inv

    def add_record(self, record: Any) -> None:
        """Adds a record (tuple, dict, or InvoiceExtraction) to the registry."""
        if isinstance(record, tuple) and len(record) >= 2:
            s_name, inv_no = record[0], record[1]
        elif isinstance(record, dict):
            s_name = record.get("supplier_name")
            inv_no = record.get("invoice_number")
        elif hasattr(record, "supplier_name") and hasattr(record, "invoice_number"):
            s_name = record.supplier_name
            inv_no = record.invoice_number
        else:
            return

        if s_name and inv_no:
            self._registry.add(self.normalize_key(s_name, inv_no))

    def is_duplicate(self, supplier_name: Optional[str], invoice_number: Optional[str]) -> bool:
        """Returns True if the normalized pair exists in the registry."""
        if not supplier_name or not invoice_number:
            return False
        return self.normalize_key(supplier_name, invoice_number) in self._registry


def verify_missing_critical_fields(invoice: InvoiceExtraction) -> List[ValidationError]:
    """
    Checks for missing critical and important invoice fields.
    Critical fields (invoice_number, invoice_date, total) trigger ERROR.
    Important fields (supplier_name) trigger WARNING.
    """
    issues: List[ValidationError] = []

    for field in CRITICAL_FIELDS:
        val = getattr(invoice, field, None)
        is_missing = (
            val is None
            or (isinstance(val, str) and not val.strip())
            or (isinstance(val, str) and val.strip().lower() in _NULL_STRINGS)
        )
        if is_missing:
            issues.append(
                ValidationError(
                    rule_id=ValidationRuleId.ANOMALY_MISSING_CRITICAL_FIELD.value,
                    field=field,
                    message=f"Critical field '{field}' is missing or null.",
                    severity=ValidationSeverity.ERROR,
                )
            )

    for field in IMPORTANT_FIELDS:
        val = getattr(invoice, field, None)
        is_missing = (
            val is None
            or (isinstance(val, str) and not val.strip())
            or (isinstance(val, str) and val.strip().lower() in _NULL_STRINGS)
        )
        if is_missing:
            issues.append(
                ValidationError(
                    rule_id=ValidationRuleId.ANOMALY_MISSING_CRITICAL_FIELD.value,
                    field=field,
                    message=f"Important field '{field}' is missing or null.",
                    severity=ValidationSeverity.WARNING,
                )
            )

    return issues


def verify_duplicate_invoice(
    invoice: InvoiceExtraction,
    existing_records: Optional[Union[Iterable[Any], DuplicateDetectorProtocol]] = None,
    is_duplicate_fn: Optional[Callable[[str, str], bool]] = None,
) -> List[ValidationError]:
    """
    Detects whether an invoice is a duplicate of a previously processed record
    based on matching supplier_name and invoice_number.
    """
    issues: List[ValidationError] = []

    if not invoice.supplier_name or not invoice.invoice_number:
        # Cannot assess duplicate status if identifiers are missing (already flagged by missing fields rule)
        return issues

    is_dup = False

    if is_duplicate_fn is not None:
        is_dup = is_duplicate_fn(invoice.supplier_name, invoice.invoice_number)
    elif existing_records is not None:
        if hasattr(existing_records, "is_duplicate"):
            is_dup = existing_records.is_duplicate(invoice.supplier_name, invoice.invoice_number)
        else:
            detector = InMemoryDuplicateDetector(existing_records)
            is_dup = detector.is_duplicate(invoice.supplier_name, invoice.invoice_number)

    if is_dup:
        issues.append(
            ValidationError(
                rule_id=ValidationRuleId.ANOMALY_DUPLICATE_INVOICE.value,
                field="invoice_number",
                message=(
                    f"Duplicate invoice detected: supplier '{invoice.supplier_name}' and "
                    f"invoice number '{invoice.invoice_number}' already exist in records."
                ),
                severity=ValidationSeverity.ERROR,
                actual=f"{invoice.supplier_name} / {invoice.invoice_number}",
            )
        )

    return issues


def _parse_date_safely(date_str: str) -> Optional[date]:
    """Attempts to parse a date string into a Python datetime.date object."""
    if not date_str or not str(date_str).strip():
        return None
    cleaned = str(date_str).strip()
    if cleaned.lower() in _NULL_STRINGS:
        return None
    try:
        # fuzzy=False avoids treating arbitrary non-date numbers as dates
        dt = date_parser.parse(cleaned, fuzzy=False)
        return dt.date()
    except (ValueError, OverflowError):
        return None


def verify_date_validity(
    invoice: InvoiceExtraction,
    reference_date: Optional[date] = None,
    min_year: int = 2000,
    max_future_days: int = 365,
) -> List[ValidationError]:
    """
    Validates calendar plausibility and chronological consistency:
      - Valid date syntax (YYYY-MM-DD, standard calendar formats)
      - Past threshold (year >= min_year)
      - Future threshold (<= reference_date + max_future_days)
      - Chronology: due_date must not precede invoice_date
    """
    issues: List[ValidationError] = []
    ref_date = reference_date or date.today()

    parsed_issue_date: Optional[date] = None
    parsed_due_date: Optional[date] = None

    # Validate issue date
    if invoice.invoice_date:
        parsed_issue_date = _parse_date_safely(invoice.invoice_date)
        if parsed_issue_date is None:
            issues.append(
                ValidationError(
                    rule_id=ValidationRuleId.ANOMALY_UNREASONABLE_DATE.value,
                    field="invoice_date",
                    message=f"Invoice date '{invoice.invoice_date}' cannot be parsed as a valid calendar date.",
                    severity=ValidationSeverity.ERROR,
                    actual=invoice.invoice_date,
                )
            )
        else:
            if parsed_issue_date.year < min_year:
                issues.append(
                    ValidationError(
                        rule_id=ValidationRuleId.ANOMALY_UNREASONABLE_DATE.value,
                        field="invoice_date",
                        message=(
                            f"Invoice date ({parsed_issue_date}) is unreasonably far in the past (year < {min_year})."
                        ),
                        severity=ValidationSeverity.WARNING,
                        actual=str(parsed_issue_date),
                    )
                )

            max_future_date = ref_date + timedelta(days=max_future_days)
            if parsed_issue_date > max_future_date:
                issues.append(
                    ValidationError(
                        rule_id=ValidationRuleId.ANOMALY_UNREASONABLE_DATE.value,
                        field="invoice_date",
                        message=(
                            f"Invoice date ({parsed_issue_date}) is unreasonably far in the future "
                            f"(> {max_future_days} days from reference date {ref_date})."
                        ),
                        severity=ValidationSeverity.WARNING,
                        actual=str(parsed_issue_date),
                    )
                )

    # Validate due date
    if invoice.due_date:
        parsed_due_date = _parse_date_safely(invoice.due_date)
        if parsed_due_date is None:
            issues.append(
                ValidationError(
                    rule_id=ValidationRuleId.ANOMALY_UNREASONABLE_DATE.value,
                    field="due_date",
                    message=f"Due date '{invoice.due_date}' cannot be parsed as a valid calendar date.",
                    severity=ValidationSeverity.WARNING,
                    actual=invoice.due_date,
                )
            )
        else:
            if parsed_due_date.year < min_year:
                issues.append(
                    ValidationError(
                        rule_id=ValidationRuleId.ANOMALY_UNREASONABLE_DATE.value,
                        field="due_date",
                        message=(
                            f"Due date ({parsed_due_date}) is unreasonably far in the past (year < {min_year})."
                        ),
                        severity=ValidationSeverity.WARNING,
                        actual=str(parsed_due_date),
                    )
                )

            max_future_date = ref_date + timedelta(days=max_future_days)
            if parsed_due_date > max_future_date:
                issues.append(
                    ValidationError(
                        rule_id=ValidationRuleId.ANOMALY_UNREASONABLE_DATE.value,
                        field="due_date",
                        message=(
                            f"Due date ({parsed_due_date}) is unreasonably far in the future "
                            f"(> {max_future_days} days from reference date {ref_date})."
                        ),
                        severity=ValidationSeverity.WARNING,
                        actual=str(parsed_due_date),
                    )
                )

    # Chronological check
    if parsed_issue_date and parsed_due_date:
        if parsed_due_date < parsed_issue_date:
            issues.append(
                ValidationError(
                    rule_id=ValidationRuleId.ANOMALY_DUE_DATE_PRECEDES_ISSUE.value,
                    field="due_date",
                    message=(
                        f"Due date ({parsed_due_date}) precedes invoice issue date ({parsed_issue_date})."
                    ),
                    severity=ValidationSeverity.ERROR,
                    expected=f">= {parsed_issue_date}",
                    actual=str(parsed_due_date),
                )
            )

    return issues


def verify_non_negative_amounts(invoice: InvoiceExtraction) -> List[ValidationError]:
    """Checks for negative financial amounts across all header fields and line items."""
    issues: List[ValidationError] = []

    for field in ("total", "subtotal", "tax"):
        val = getattr(invoice, field, None)
        if val is not None and isinstance(val, Decimal) and val < Decimal("0.00"):
            issues.append(
                ValidationError(
                    rule_id=ValidationRuleId.ANOMALY_NEGATIVE_AMOUNT.value,
                    field=field,
                    message=f"Financial amount for '{field}' cannot be negative: {val}.",
                    severity=ValidationSeverity.ERROR,
                    expected=">= 0.00",
                    actual=str(val),
                )
            )

    for idx, item in enumerate(invoice.line_items):
        for num_field in ("amount", "unit_price", "quantity"):
            val = getattr(item, num_field, None)
            if val is not None and isinstance(val, Decimal) and val < Decimal("0.00"):
                issues.append(
                    ValidationError(
                        rule_id=ValidationRuleId.ANOMALY_NEGATIVE_AMOUNT.value,
                        field=f"line_items[{idx}].{num_field}",
                        message=f"Line item {idx + 1} '{num_field}' cannot be negative: {val}.",
                        severity=ValidationSeverity.ERROR,
                        expected=">= 0.00",
                        actual=str(val),
                    )
                )

    return issues


def run_all_anomaly_rules(
    invoice: InvoiceExtraction,
    existing_records: Optional[Union[Iterable[Any], DuplicateDetectorProtocol]] = None,
    is_duplicate_fn: Optional[Callable[[str, str], bool]] = None,
    reference_date: Optional[date] = None,
    min_year: int = 2000,
    max_future_days: int = 365,
) -> List[ValidationError]:
    """Runs all integrity and anomaly rules and returns discovered errors and warnings."""
    all_issues: List[ValidationError] = []
    all_issues.extend(verify_missing_critical_fields(invoice))
    all_issues.extend(verify_duplicate_invoice(invoice, existing_records=existing_records, is_duplicate_fn=is_duplicate_fn))
    all_issues.extend(
        verify_date_validity(
            invoice,
            reference_date=reference_date,
            min_year=min_year,
            max_future_days=max_future_days,
        )
    )
    all_issues.extend(verify_non_negative_amounts(invoice))
    return all_issues
