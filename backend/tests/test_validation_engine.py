"""
Comprehensive test suite for TASK-008: Deterministic Financial Validation Engine.
Tests mathematical consistency, integrity anomalies, date validity, duplicate detection,
boundary conditions, and overall workflow status determination (VERIFIED, NEEDS_REVIEW, FAILED).
"""
from datetime import date, timedelta
from decimal import Decimal
import json
import pytest

from apps.extraction.schemas import InvoiceExtraction, LineItemExtraction
from apps.validation import (
    DEFAULT_TOLERANCE,
    InMemoryDuplicateDetector,
    ValidationError,
    ValidationEngine,
    ValidationResult,
    ValidationRuleId,
    ValidationSeverity,
    ValidationStatus,
    run_all_anomaly_rules,
    run_all_math_rules,
    verify_date_validity,
    verify_duplicate_invoice,
    verify_line_item_calculations,
    verify_line_item_sum,
    verify_missing_critical_fields,
    verify_non_negative_amounts,
    verify_tax_addition,
)


def make_valid_invoice(**kwargs) -> InvoiceExtraction:
    """Helper to construct a valid base invoice."""
    defaults = {
        "invoice_number": "INV-2026-001",
        "invoice_date": "2026-05-10",
        "due_date": "2026-06-10",
        "supplier_name": "Acme Industrial Supplies LLC",
        "supplier_address": "123 Manufacturing Way, Chicago, IL 60601",
        "customer_name": "Global Logistics Corp",
        "customer_address": "789 Freight Ave, Dallas, TX 75201",
        "subtotal": Decimal("1000.00"),
        "tax": Decimal("82.50"),
        "total": Decimal("1082.50"),
        "currency": "USD",
        "line_items": [
            LineItemExtraction(
                description="Heavy Duty Industrial Valve",
                quantity=Decimal("2"),
                unit_price=Decimal("300.00"),
                amount=Decimal("600.00"),
            ),
            LineItemExtraction(
                description="High Pressure Flange Set",
                quantity=Decimal("4"),
                unit_price=Decimal("100.00"),
                amount=Decimal("400.00"),
            ),
        ],
    }
    defaults.update(kwargs)
    return InvoiceExtraction(**defaults)


# =========================================================================
# 1. Mathematical Rules Tests & Boundary Precision
# =========================================================================

class TestMathematicalRules:
    """Tests for Line Item Sum, Tax Addition, and Itemized Arithmetic calculations."""

    def test_line_item_sum_exact_match(self):
        invoice = make_valid_invoice()
        issues = verify_line_item_sum(invoice)
        assert len(issues) == 0

    def test_line_item_sum_exact_tolerance_boundary_0_05(self):
        # Exactly 0.05 difference passes
        invoice = make_valid_invoice(subtotal=Decimal("1000.05"))
        issues = verify_line_item_sum(invoice, tolerance=Decimal("0.05"))
        assert len(issues) == 0

    def test_line_item_sum_just_above_tolerance_boundary_0_05001_fails(self):
        # Just above 0.05 difference fails
        invoice = make_valid_invoice(subtotal=Decimal("1000.051"))
        issues = verify_line_item_sum(invoice, tolerance=Decimal("0.05"))
        assert len(issues) == 1
        assert issues[0].rule_id == ValidationRuleId.MATH_LINE_ITEM_SUM.value
        assert issues[0].severity == ValidationSeverity.ERROR

    def test_line_item_sum_float_tolerance_coercion_safe(self):
        # Calling with float tolerance does not crash with TypeError
        invoice = make_valid_invoice(subtotal=Decimal("1000.04"))
        issues = verify_line_item_sum(invoice, tolerance=0.05)
        assert len(issues) == 0

    def test_line_item_sum_missing_amounts_computed_from_qty_and_price(self):
        # Item 1 has no amount, but quantity=2 and unit_price=300 (computes to 600.00)
        invoice = make_valid_invoice(
            line_items=[
                LineItemExtraction(description="Part A", quantity=Decimal("2"), unit_price=Decimal("300.00"), amount=None),
                LineItemExtraction(description="Part B", quantity=Decimal("4"), unit_price=Decimal("100.00"), amount=Decimal("400.00")),
            ]
        )
        issues = verify_line_item_sum(invoice)
        assert len(issues) == 0

    def test_line_item_sum_indeterminate_item_warns_and_prevents_false_success(self):
        # Item has no amount and no unit price
        invoice = make_valid_invoice(
            subtotal=Decimal("600.00"),
            line_items=[
                LineItemExtraction(description="Known Item", quantity=Decimal("2"), unit_price=Decimal("300.00"), amount=Decimal("600.00")),
                LineItemExtraction(description="Unpriced Service", quantity=Decimal("1"), unit_price=None, amount=None),
            ]
        )
        issues = verify_line_item_sum(invoice)
        # Must warn about indeterminate sum and incomplete item
        assert any(i.severity == ValidationSeverity.WARNING and "incomplete" in i.message for i in issues)
        assert any(i.severity == ValidationSeverity.WARNING and "cannot definitively verify" in i.message for i in issues)

    def test_line_item_sum_indeterminate_item_already_exceeding_subtotal_fails(self):
        # Known item is 700, subtotal is 600, plus an unpriced item -> known already exceeds subtotal
        invoice = make_valid_invoice(
            subtotal=Decimal("600.00"),
            line_items=[
                LineItemExtraction(description="Known Item", quantity=Decimal("1"), unit_price=Decimal("700.00"), amount=Decimal("700.00")),
                LineItemExtraction(description="Unpriced Service", quantity=Decimal("1"), unit_price=None, amount=None),
            ]
        )
        issues = verify_line_item_sum(invoice)
        assert any(i.severity == ValidationSeverity.ERROR and "exceeds" in i.message for i in issues)

    def test_line_item_sum_no_line_items_warns(self):
        invoice = make_valid_invoice(line_items=[])
        issues = verify_line_item_sum(invoice)
        assert len(issues) == 1
        assert issues[0].severity == ValidationSeverity.WARNING

    def test_tax_addition_exact_match(self):
        invoice = make_valid_invoice(
            subtotal=Decimal("500.00"),
            tax=Decimal("50.00"),
            total=Decimal("550.00"),
        )
        issues = verify_tax_addition(invoice)
        assert len(issues) == 0

    def test_tax_addition_exact_tolerance_boundary_0_05(self):
        invoice = make_valid_invoice(
            subtotal=Decimal("500.00"),
            tax=Decimal("50.00"),
            total=Decimal("550.05"),  # diff exactly 0.05
        )
        issues = verify_tax_addition(invoice, tolerance=Decimal("0.05"))
        assert len(issues) == 0

    def test_tax_addition_just_above_tolerance_boundary_0_051_fails(self):
        invoice = make_valid_invoice(
            subtotal=Decimal("500.00"),
            tax=Decimal("50.00"),
            total=Decimal("550.051"),  # diff > 0.05
        )
        issues = verify_tax_addition(invoice, tolerance=Decimal("0.05"))
        assert len(issues) == 1
        assert issues[0].rule_id == ValidationRuleId.MATH_TAX_ADDITION.value
        assert issues[0].severity == ValidationSeverity.ERROR

    def test_tax_addition_explicit_zero_tax_verified(self):
        # Stated tax is explicitly 0.00
        invoice = make_valid_invoice(
            subtotal=Decimal("500.00"),
            tax=Decimal("0.00"),
            total=Decimal("500.00"),
        )
        issues = verify_tax_addition(invoice)
        assert len(issues) == 0

    def test_tax_addition_null_tax_when_subtotal_equals_total_warns_for_review(self):
        # Tax is null, subtotal equals total -> not assumed zero, flags warning for human review
        invoice = make_valid_invoice(
            subtotal=Decimal("500.00"),
            tax=None,
            total=Decimal("500.00"),
        )
        issues = verify_tax_addition(invoice)
        assert len(issues) == 1
        assert issues[0].rule_id == ValidationRuleId.MATH_TAX_ADDITION.value
        assert issues[0].severity == ValidationSeverity.WARNING
        assert "tax exemption requires operator review" in issues[0].message.lower()

    def test_tax_addition_null_tax_when_subtotal_differs_from_total_fails(self):
        # Tax is null, subtotal does not match total -> fails
        invoice = make_valid_invoice(
            subtotal=Decimal("500.00"),
            tax=None,
            total=Decimal("550.00"),
        )
        issues = verify_tax_addition(invoice)
        assert len(issues) == 1
        assert issues[0].rule_id == ValidationRuleId.MATH_TAX_ADDITION.value
        assert issues[0].severity == ValidationSeverity.ERROR

    def test_tax_addition_negative_tax_fails(self):
        invoice = make_valid_invoice(
            subtotal=Decimal("500.00"),
            total=Decimal("475.00"),
        )
        object.__setattr__(invoice, "tax", Decimal("-25.00"))
        issues = verify_tax_addition(invoice)
        assert any(i.field == "tax" and "negative" in i.message.lower() for i in issues)

    def test_tax_addition_tax_exceeds_total_fails(self):
        invoice = make_valid_invoice(
            subtotal=Decimal("50.00"),
            tax=Decimal("150.00"),
            total=Decimal("100.00"),
        )
        issues = verify_tax_addition(invoice)
        assert any(i.field == "tax" and "exceeds" in i.message for i in issues)

    def test_tax_addition_missing_subtotal_warns(self):
        invoice = make_valid_invoice(
            subtotal=None,
            tax=Decimal("20.00"),
            total=Decimal("220.00"),
            line_items=[],
        )
        issues = verify_tax_addition(invoice)
        assert any(i.field == "subtotal" and i.severity == ValidationSeverity.WARNING for i in issues)

    def test_line_item_calculation_exact_match(self):
        invoice = make_valid_invoice()
        issues = verify_line_item_calculations(invoice)
        assert len(issues) == 0

    def test_line_item_calculation_exact_tolerance_boundary_0_05(self):
        invoice = make_valid_invoice(
            line_items=[
                LineItemExtraction(
                    description="Item A",
                    quantity=Decimal("3"),
                    unit_price=Decimal("10.00"),
                    amount=Decimal("30.05"),  # diff exactly 0.05
                )
            ]
        )
        issues = verify_line_item_calculations(invoice, tolerance=Decimal("0.05"))
        assert len(issues) == 0

    def test_line_item_calculation_just_above_tolerance_0_051_fails(self):
        invoice = make_valid_invoice(
            line_items=[
                LineItemExtraction(
                    description="Item A",
                    quantity=Decimal("3"),
                    unit_price=Decimal("10.00"),
                    amount=Decimal("30.051"),  # diff > 0.05
                )
            ]
        )
        issues = verify_line_item_calculations(invoice, tolerance=Decimal("0.05"))
        assert len(issues) == 1
        assert issues[0].rule_id == ValidationRuleId.MATH_ITEM_CALCULATION.value
        assert issues[0].severity == ValidationSeverity.ERROR


# =========================================================================
# 2. Integrity and Anomaly Rules Tests
# =========================================================================

class TestAnomalyAndIntegrityRules:
    """Tests for Critical Fields, Duplicate Detection, Date Plausibility, and Negative Numbers."""

    def test_missing_critical_invoice_number_fails(self):
        invoice = make_valid_invoice(invoice_number=None)
        issues = verify_missing_critical_fields(invoice)
        assert any(i.field == "invoice_number" and i.severity == ValidationSeverity.ERROR for i in issues)

    def test_whitespace_only_invoice_number_fails(self):
        invoice = make_valid_invoice(invoice_number="   ")
        issues = verify_missing_critical_fields(invoice)
        assert any(i.field == "invoice_number" and i.severity == ValidationSeverity.ERROR for i in issues)

    def test_literal_na_string_invoice_number_fails(self):
        invoice = make_valid_invoice(invoice_number="N/A")
        issues = verify_missing_critical_fields(invoice)
        assert any(i.field == "invoice_number" and i.severity == ValidationSeverity.ERROR for i in issues)

    def test_missing_critical_invoice_date_fails(self):
        invoice = make_valid_invoice(invoice_date=None)
        issues = verify_missing_critical_fields(invoice)
        assert any(i.field == "invoice_date" and i.severity == ValidationSeverity.ERROR for i in issues)

    def test_missing_critical_total_fails(self):
        invoice = make_valid_invoice(total=None)
        issues = verify_missing_critical_fields(invoice)
        assert any(i.field == "total" and i.severity == ValidationSeverity.ERROR for i in issues)

    def test_missing_important_supplier_name_warns(self):
        invoice = make_valid_invoice(supplier_name=None)
        issues = verify_missing_critical_fields(invoice)
        assert any(i.field == "supplier_name" and i.severity == ValidationSeverity.WARNING for i in issues)

    def test_duplicate_invoice_detected_via_tuple_list(self):
        invoice = make_valid_invoice(
            supplier_name="Acme Corp",
            invoice_number="INV-9999",
        )
        existing = [
            ("Other Supplier", "INV-1111"),
            ("Acme Corp", "INV-9999"),
        ]
        issues = verify_duplicate_invoice(invoice, existing_records=existing)
        assert len(issues) == 1
        assert issues[0].rule_id == ValidationRuleId.ANOMALY_DUPLICATE_INVOICE.value
        assert issues[0].severity == ValidationSeverity.ERROR

    def test_duplicate_invoice_case_and_whitespace_insensitivity(self):
        invoice = make_valid_invoice(
            supplier_name="  ACME   CORP.  ",
            invoice_number="inv-9999",
        )
        existing = [("acme corp", "INV-9999")]
        issues = verify_duplicate_invoice(invoice, existing_records=existing)
        assert len(issues) == 1
        assert issues[0].rule_id == ValidationRuleId.ANOMALY_DUPLICATE_INVOICE.value

    def test_duplicate_detection_preserves_internal_punctuation_preventing_false_duplicates(self):
        # Distinct entities like "C# Tech" vs "C Tech" must NOT be treated as duplicates
        invoice = make_valid_invoice(
            supplier_name="C# Tech",
            invoice_number="INV-100",
        )
        existing = [("C Tech", "INV-100")]
        issues = verify_duplicate_invoice(invoice, existing_records=existing)
        assert len(issues) == 0

    def test_duplicate_detection_preserves_invoice_number_symbols_preventing_false_duplicates(self):
        # "INV-01" vs "INV01" are distinct invoice numbers
        invoice = make_valid_invoice(
            supplier_name="Acme Corp",
            invoice_number="INV-01",
        )
        existing = [("Acme Corp", "INV01")]
        issues = verify_duplicate_invoice(invoice, existing_records=existing)
        assert len(issues) == 0

    def test_duplicate_invoice_detected_via_callable(self):
        invoice = make_valid_invoice(supplier_name="Acme Corp", invoice_number="INV-123")
        is_dup_fn = lambda s, num: s == "Acme Corp" and num == "INV-123"
        issues = verify_duplicate_invoice(invoice, is_duplicate_fn=is_dup_fn)
        assert len(issues) == 1
        assert issues[0].rule_id == ValidationRuleId.ANOMALY_DUPLICATE_INVOICE.value

    def test_non_duplicate_invoice_passes(self):
        invoice = make_valid_invoice(supplier_name="Acme Corp", invoice_number="INV-NEW")
        detector = InMemoryDuplicateDetector([("Acme Corp", "INV-OLD")])
        issues = verify_duplicate_invoice(invoice, existing_records=detector)
        assert len(issues) == 0

    def test_valid_calendar_dates_pass(self):
        invoice = make_valid_invoice(
            invoice_date="2026-05-15",
            due_date="2026-06-15",
        )
        issues = verify_date_validity(invoice, reference_date=date(2026, 5, 15))
        assert len(issues) == 0

    def test_date_year_2000_exact_boundary_passes(self):
        invoice = make_valid_invoice(invoice_date="2000-01-01", due_date="2000-02-01")
        issues = verify_date_validity(invoice, reference_date=date(2000, 1, 1), min_year=2000)
        assert len(issues) == 0

    def test_date_year_1999_before_min_year_warns(self):
        invoice = make_valid_invoice(invoice_date="1999-12-31")
        issues = verify_date_validity(invoice, reference_date=date(2000, 1, 1), min_year=2000)
        assert any(i.field == "invoice_date" and i.severity == ValidationSeverity.WARNING and "past" in i.message for i in issues)

    def test_date_exactly_365_days_future_boundary_passes(self):
        ref = date(2026, 1, 1)
        future_date = (ref + timedelta(days=365)).isoformat()
        invoice = make_valid_invoice(invoice_date=future_date, due_date=future_date)
        issues = verify_date_validity(invoice, reference_date=ref, max_future_days=365)
        assert len(issues) == 0

    def test_date_366_days_future_boundary_warns(self):
        ref = date(2026, 1, 1)
        future_date = (ref + timedelta(days=366)).isoformat()
        invoice = make_valid_invoice(invoice_date=future_date)
        issues = verify_date_validity(invoice, reference_date=ref, max_future_days=365)
        assert any(i.field == "invoice_date" and i.severity == ValidationSeverity.WARNING and "future" in i.message for i in issues)

    def test_due_date_far_future_warns(self):
        ref = date(2026, 1, 1)
        invoice = make_valid_invoice(invoice_date="2026-01-10", due_date="2029-01-01")
        issues = verify_date_validity(invoice, reference_date=ref, max_future_days=365)
        assert any(i.field == "due_date" and i.severity == ValidationSeverity.WARNING and "future" in i.message for i in issues)

    def test_unparseable_invoice_date_fails(self):
        invoice = make_valid_invoice(invoice_date="invalid-date-string")
        issues = verify_date_validity(invoice)
        assert any(i.field == "invoice_date" and i.severity == ValidationSeverity.ERROR for i in issues)

    def test_unparseable_due_date_warns(self):
        invoice = make_valid_invoice(due_date="not-a-valid-due-date")
        issues = verify_date_validity(invoice)
        assert any(i.field == "due_date" and i.severity == ValidationSeverity.WARNING for i in issues)

    def test_chronological_contradiction_due_date_before_invoice_date_fails(self):
        invoice = make_valid_invoice(
            invoice_date="2026-06-15",
            due_date="2026-05-15",  # Due date is one month before invoice date
        )
        issues = verify_date_validity(invoice)
        assert any(i.rule_id == ValidationRuleId.ANOMALY_DUE_DATE_PRECEDES_ISSUE.value for i in issues)
        assert any(i.severity == ValidationSeverity.ERROR for i in issues)

    def test_negative_amounts_detected(self):
        invoice = make_valid_invoice()
        object.__setattr__(invoice, "total", Decimal("-100.00"))
        issues = verify_non_negative_amounts(invoice)
        assert any(i.field == "total" and i.rule_id == ValidationRuleId.ANOMALY_NEGATIVE_AMOUNT.value for i in issues)


# =========================================================================
# 3. ValidationEngine End-to-End Orchestration Tests
# =========================================================================

class TestValidationEngineOrchestration:
    """Tests for the overall ValidationEngine workflow, status precedence, and serialization."""

    def test_perfect_invoice_status_verified(self):
        engine = ValidationEngine()
        invoice = make_valid_invoice()
        result = engine.validate(invoice)

        assert result.status == ValidationStatus.VERIFIED
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
        assert "successfully verified" in result.summary.lower()

    def test_arithmetic_discrepancy_status_failed(self):
        engine = ValidationEngine()
        invoice = make_valid_invoice(subtotal=Decimal("950.00"))  # Items sum to 1000.00
        result = engine.validate(invoice)

        assert result.status == ValidationStatus.FAILED
        assert result.is_valid is False
        assert len(result.errors) >= 1
        assert any(e.rule_id == ValidationRuleId.MATH_LINE_ITEM_SUM.value for e in result.errors)

    def test_warning_only_invoice_status_needs_review(self):
        engine = ValidationEngine()
        # Missing supplier_name triggers WARNING; no mathematical errors
        invoice = make_valid_invoice(supplier_name=None)
        result = engine.validate(invoice)

        assert result.status == ValidationStatus.NEEDS_REVIEW
        assert result.is_valid is False
        assert len(result.errors) == 0
        assert len(result.warnings) == 1
        assert result.warnings[0].field == "supplier_name"

    def test_status_precedence_errors_override_warnings(self):
        engine = ValidationEngine()
        # Has both warning (missing supplier_name) and error (missing invoice_number)
        invoice = make_valid_invoice(supplier_name=None, invoice_number=None)
        result = engine.validate(invoice)

        assert result.status == ValidationStatus.FAILED
        assert result.is_valid is False
        assert len(result.errors) >= 1
        assert len(result.warnings) >= 1

    def test_duplicate_invoice_status_failed(self):
        existing = [("Acme Industrial Supplies LLC", "INV-2026-001")]
        engine = ValidationEngine()
        invoice = make_valid_invoice()
        result = engine.validate(invoice, existing_records=existing)

        assert result.status == ValidationStatus.FAILED
        assert any(e.rule_id == ValidationRuleId.ANOMALY_DUPLICATE_INVOICE.value for e in result.errors)

    def test_validate_from_dict_input(self):
        engine = ValidationEngine()
        invoice_dict = make_valid_invoice().model_dump()
        result = engine.validate(invoice_dict)

        assert result.status == ValidationStatus.VERIFIED
        assert result.is_valid is True

    def test_validate_from_dict_with_negative_total_fails_controlled(self):
        engine = ValidationEngine()
        invoice_dict = make_valid_invoice().model_dump()
        invoice_dict["total"] = -150.00
        result = engine.validate(invoice_dict)

        assert result.status == ValidationStatus.FAILED
        assert result.is_valid is False
        assert len(result.errors) >= 1
        assert result.errors[0].rule_id == ValidationRuleId.ANOMALY_SCHEMA_VIOLATION.value

    def test_validate_from_json_string(self):
        engine = ValidationEngine()
        invoice_json = json.dumps(make_valid_invoice().model_dump(mode="json"))
        result = engine.validate(invoice_json)

        assert result.status == ValidationStatus.VERIFIED
        assert result.is_valid is True

    def test_validate_malformed_json_returns_failed_result_without_crash(self):
        engine = ValidationEngine()
        result = engine.validate("{bad json:")

        assert result.status == ValidationStatus.FAILED
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].rule_id == ValidationRuleId.ANOMALY_SCHEMA_VIOLATION.value

    def test_validate_unsupported_input_type_returns_failed_result(self):
        engine = ValidationEngine()
        result = engine.validate(12345)  # Integer is invalid

        assert result.status == ValidationStatus.FAILED
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].rule_id == ValidationRuleId.ANOMALY_SCHEMA_VIOLATION.value

    def test_result_to_dict_serialization_purity(self):
        engine = ValidationEngine()
        invoice = make_valid_invoice()
        result = engine.validate(invoice)
        res_dict = result.to_dict()

        assert res_dict["status"] == "VERIFIED"
        assert res_dict["is_valid"] is True
        assert isinstance(res_dict["rules_checked"], list)
        assert len(res_dict["rules_checked"]) > 5
        assert isinstance(res_dict["errors"], list)
        assert isinstance(res_dict["warnings"], list)
        # Validate JSON serialization roundtrip
        serialized = json.dumps(res_dict)
        deserialized = json.loads(serialized)
        assert deserialized["status"] == "VERIFIED"
