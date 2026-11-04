"""
DocuMind AI Deterministic Financial Validation Package.
Exports the ValidationEngine, rule definitions, and data models.
"""
from .models import (
    ValidationError,
    ValidationResult,
    ValidationRuleId,
    ValidationSeverity,
    ValidationStatus,
)
from .math_rules import (
    DEFAULT_TOLERANCE,
    run_all_math_rules,
    verify_line_item_calculations,
    verify_line_item_sum,
    verify_tax_addition,
)
from .anomaly_rules import (
    DuplicateDetectorProtocol,
    InMemoryDuplicateDetector,
    run_all_anomaly_rules,
    verify_date_validity,
    verify_duplicate_invoice,
    verify_missing_critical_fields,
    verify_non_negative_amounts,
)
from .engine import ValidationEngine

__all__ = [
    "ValidationStatus",
    "ValidationSeverity",
    "ValidationRuleId",
    "ValidationError",
    "ValidationResult",
    "DEFAULT_TOLERANCE",
    "verify_line_item_sum",
    "verify_tax_addition",
    "verify_line_item_calculations",
    "run_all_math_rules",
    "DuplicateDetectorProtocol",
    "InMemoryDuplicateDetector",
    "verify_missing_critical_fields",
    "verify_duplicate_invoice",
    "verify_date_validity",
    "verify_non_negative_amounts",
    "run_all_anomaly_rules",
    "ValidationEngine",
]

