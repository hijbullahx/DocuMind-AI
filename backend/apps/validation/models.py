"""
Data contracts and error models for the Deterministic Validation Engine.
Defines ValidationStatus, ValidationSeverity, ValidationRuleId, ValidationError, and ValidationResult.
"""
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ValidationStatus(str, Enum):
    """Workflow status for validated invoice documents."""
    VERIFIED = "VERIFIED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FAILED = "FAILED"


class ValidationSeverity(str, Enum):
    """Severity level of an individual validation finding."""
    ERROR = "ERROR"        # Causes validation to fail (Status -> FAILED)
    WARNING = "WARNING"    # Non-critical issue requiring human review (Status -> NEEDS_REVIEW)
    INFO = "INFO"          # Informational note (does not degrade status)


class ValidationRuleId(str, Enum):
    """Unique rule identifiers for deterministic validation checks."""
    # Mathematical rules
    MATH_LINE_ITEM_SUM = "MATH_LINE_ITEM_SUM"
    MATH_TAX_ADDITION = "MATH_TAX_ADDITION"
    MATH_ITEM_CALCULATION = "MATH_ITEM_CALCULATION"

    # Integrity & Anomaly rules
    ANOMALY_MISSING_CRITICAL_FIELD = "ANOMALY_MISSING_CRITICAL_FIELD"
    ANOMALY_DUPLICATE_INVOICE = "ANOMALY_DUPLICATE_INVOICE"
    ANOMALY_UNREASONABLE_DATE = "ANOMALY_UNREASONABLE_DATE"
    ANOMALY_DUE_DATE_PRECEDES_ISSUE = "ANOMALY_DUE_DATE_PRECEDES_ISSUE"
    ANOMALY_NEGATIVE_AMOUNT = "ANOMALY_NEGATIVE_AMOUNT"
    ANOMALY_SCHEMA_VIOLATION = "ANOMALY_SCHEMA_VIOLATION"


class ValidationError(BaseModel):
    """
    Actionable validation error or warning with rule ID, target field,
    expected vs actual values, and computed arithmetic discrepancy.
    """
    rule_id: str = Field(..., description="Validation rule identifier string or ValidationRuleId")
    field: Optional[str] = Field(None, description="Field name or JSON path associated with this issue")
    message: str = Field(..., description="Human-readable description of the discrepancy or rule failure")
    severity: ValidationSeverity = Field(
        default=ValidationSeverity.ERROR,
        description="Severity level (ERROR fails document, WARNING marks for review)"
    )
    expected: Optional[str] = Field(None, description="Expected value (e.g. calculated sum or valid format)")
    actual: Optional[str] = Field(None, description="Actual value extracted from the invoice")
    difference: Optional[Decimal] = Field(None, description="Absolute arithmetic difference if applicable")

    def to_dict(self) -> Dict[str, Any]:
        """Serializes error to dictionary with Decimal values stringified or preserved."""
        return {
            "rule_id": str(self.rule_id),
            "field": self.field,
            "message": self.message,
            "severity": self.severity.value,
            "expected": self.expected,
            "actual": self.actual,
            "difference": str(self.difference) if self.difference is not None else None,
        }


class ValidationResult(BaseModel):
    """
    Aggregate result returned by the Validation Engine for an invoice.
    Consolidates workflow status, discrete errors, warnings, and checked rules.
    """
    status: ValidationStatus = Field(..., description="Workflow status: VERIFIED, NEEDS_REVIEW, or FAILED")
    is_valid: bool = Field(..., description="True if status is VERIFIED (no errors or warnings)")
    errors: List[ValidationError] = Field(default_factory=list, description="Critical validation errors")
    warnings: List[ValidationError] = Field(default_factory=list, description="Non-critical review warnings")
    rules_checked: List[str] = Field(default_factory=list, description="List of all validation rules evaluated")
    summary: str = Field(default="", description="Concise human-readable summary of validation outcome")

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the result to a dictionary representation."""
        return {
            "status": self.status.value,
            "is_valid": self.is_valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "rules_checked": self.rules_checked,
            "summary": self.summary,
        }

