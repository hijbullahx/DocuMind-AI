"""
Deterministic Financial Validation Engine for DocuMind-AI.
Coordinates mathematical consistency and business integrity anomaly rules.
Returns structured ValidationResult with status VERIFIED, NEEDS_REVIEW, or FAILED.
"""
from datetime import date
from decimal import Decimal
from typing import Any, Callable, Dict, Iterable, List, Optional, Union

from apps.extraction.schemas import ExtractionSchemaError, InvoiceExtraction
from .anomaly_rules import (
    DuplicateDetectorProtocol,
    InMemoryDuplicateDetector,
    run_all_anomaly_rules,
)
from .math_rules import (
    DEFAULT_TOLERANCE,
    run_all_math_rules,
)
from .models import (
    ValidationError,
    ValidationResult,
    ValidationRuleId,
    ValidationSeverity,
    ValidationStatus,
)


class ValidationEngine:
    """
    Deterministic Financial Validation Engine.
    Executes rules in strict order:
      1. Schema parsing and defensive coercion
      2. Anomaly rules (critical fields, duplicate invoices, date plausibility, negative numbers)
      3. Mathematical rules (line item arithmetic, line items sum, subtotal + tax = total)
    """

    def __init__(
        self,
        default_tolerance: Decimal = DEFAULT_TOLERANCE,
        duplicate_detector: Optional[DuplicateDetectorProtocol] = None,
        reference_date: Optional[date] = None,
        min_year: int = 2000,
        max_future_days: int = 365,
    ):
        self.default_tolerance = default_tolerance
        self.duplicate_detector = duplicate_detector
        self.reference_date = reference_date
        self.min_year = min_year
        self.max_future_days = max_future_days

    def validate(
        self,
        invoice_data: Union[InvoiceExtraction, Dict[str, Any], str],
        existing_records: Optional[Union[Iterable[Any], DuplicateDetectorProtocol]] = None,
        is_duplicate_fn: Optional[Callable[[str, str], bool]] = None,
        tolerance: Optional[Decimal] = None,
        reference_date: Optional[date] = None,
    ) -> ValidationResult:
        """
        Validates an extracted invoice and returns a comprehensive ValidationResult.

        Args:
            invoice_data: An InvoiceExtraction model, raw dictionary, or raw JSON string.
            existing_records: Optional iterable of prior invoice records for duplicate checking.
            is_duplicate_fn: Optional custom callable (supplier, inv_no) -> bool.
            tolerance: Custom arithmetic discrepancy tolerance (defaults to self.default_tolerance).
            reference_date: Custom date reference for future date evaluations (defaults to self.reference_date or today).

        Returns:
            ValidationResult with status VERIFIED, NEEDS_REVIEW, or FAILED.
        """
        rules_checked: List[str] = [
            ValidationRuleId.ANOMALY_SCHEMA_VIOLATION.value,
            ValidationRuleId.ANOMALY_MISSING_CRITICAL_FIELD.value,
            ValidationRuleId.ANOMALY_DUPLICATE_INVOICE.value,
            ValidationRuleId.ANOMALY_UNREASONABLE_DATE.value,
            ValidationRuleId.ANOMALY_DUE_DATE_PRECEDES_ISSUE.value,
            ValidationRuleId.ANOMALY_NEGATIVE_AMOUNT.value,
            ValidationRuleId.MATH_ITEM_CALCULATION.value,
            ValidationRuleId.MATH_LINE_ITEM_SUM.value,
            ValidationRuleId.MATH_TAX_ADDITION.value,
        ]

        active_tolerance = (
            Decimal(str(tolerance)) if tolerance is not None
            else (self.default_tolerance if isinstance(self.default_tolerance, Decimal) else Decimal(str(self.default_tolerance)))
        )
        active_ref_date = reference_date or self.reference_date or date.today()
        active_dup_detector = existing_records if existing_records is not None else self.duplicate_detector

        # Step 1: Input coercion to InvoiceExtraction
        invoice: InvoiceExtraction
        if isinstance(invoice_data, InvoiceExtraction):
            invoice = invoice_data
        elif isinstance(invoice_data, dict):
            try:
                invoice = InvoiceExtraction.model_validate(invoice_data)
            except Exception as e:
                err = ValidationError(
                    rule_id=ValidationRuleId.ANOMALY_SCHEMA_VIOLATION.value,
                    message=f"Invoice data failed schema validation: {e}",
                    severity=ValidationSeverity.ERROR,
                )
                return ValidationResult(
                    status=ValidationStatus.FAILED,
                    is_valid=False,
                    errors=[err],
                    warnings=[],
                    rules_checked=[ValidationRuleId.ANOMALY_SCHEMA_VIOLATION.value],
                    summary=f"Validation failed: schema validation error ({e})",
                )
        elif isinstance(invoice_data, str):
            try:
                invoice = InvoiceExtraction.from_raw_json(invoice_data)
            except ExtractionSchemaError as e:
                err = ValidationError(
                    rule_id=ValidationRuleId.ANOMALY_SCHEMA_VIOLATION.value,
                    message=f"Raw model response failed JSON/schema parsing: {e}",
                    severity=ValidationSeverity.ERROR,
                )
                return ValidationResult(
                    status=ValidationStatus.FAILED,
                    is_valid=False,
                    errors=[err],
                    warnings=[],
                    rules_checked=[ValidationRuleId.ANOMALY_SCHEMA_VIOLATION.value],
                    summary=f"Validation failed: unparseable JSON/schema error ({e})",
                )
        else:
            err = ValidationError(
                rule_id=ValidationRuleId.ANOMALY_SCHEMA_VIOLATION.value,
                message=f"Unsupported input type for validation: {type(invoice_data).__name__}",
                severity=ValidationSeverity.ERROR,
            )
            return ValidationResult(
                status=ValidationStatus.FAILED,
                is_valid=False,
                errors=[err],
                warnings=[],
                rules_checked=[ValidationRuleId.ANOMALY_SCHEMA_VIOLATION.value],
                summary="Validation failed: unsupported input type.",
            )

        # Step 2: Execute Anomaly and Integrity Rules
        anomaly_issues = run_all_anomaly_rules(
            invoice=invoice,
            existing_records=active_dup_detector,
            is_duplicate_fn=is_duplicate_fn,
            reference_date=active_ref_date,
            min_year=self.min_year,
            max_future_days=self.max_future_days,
        )

        # Step 3: Execute Mathematical Rules
        math_issues = run_all_math_rules(
            invoice=invoice,
            tolerance=active_tolerance,
        )

        all_issues = anomaly_issues + math_issues
        errors = [i for i in all_issues if i.severity == ValidationSeverity.ERROR]
        warnings = [i for i in all_issues if i.severity == ValidationSeverity.WARNING]

        # Step 4: Determine Workflow Status
        if errors:
            status = ValidationStatus.FAILED
            is_valid = False
            summary = f"Validation failed with {len(errors)} critical error(s)."
        elif warnings:
            status = ValidationStatus.NEEDS_REVIEW
            is_valid = False
            summary = f"Validation requires human review: {len(warnings)} warning(s) flagged."
        else:
            status = ValidationStatus.VERIFIED
            is_valid = True
            summary = "Invoice successfully verified. All arithmetic and integrity checks passed."

        return ValidationResult(
            status=status,
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            rules_checked=rules_checked,
            summary=summary,
        )

