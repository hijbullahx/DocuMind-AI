"""
Deterministic Mathematical Validation Rules for DocuMind-AI.
Enforces arithmetic consistency across invoices using exact Decimal precision:
  1. Line Item Sum Check: |sum(line_item.amount) - subtotal| <= 0.05
  2. Tax Addition Check: |subtotal + tax - total| <= 0.05
  3. Quantity x Unit Price Check: |quantity * unit_price - amount| <= 0.05
"""
from decimal import Decimal
from typing import List, Optional, Union

from apps.extraction.schemas import InvoiceExtraction, LineItemExtraction
from .models import ValidationError, ValidationRuleId, ValidationSeverity

DEFAULT_TOLERANCE: Decimal = Decimal("0.05")


def _coerce_tolerance(tolerance: Union[Decimal, float, str, int]) -> Decimal:
    """Safely converts tolerance to Decimal to avoid binary float comparison errors."""
    if isinstance(tolerance, Decimal):
        return tolerance
    return Decimal(str(tolerance))


def verify_line_item_sum(
    invoice: InvoiceExtraction,
    tolerance: Union[Decimal, float, str, int] = DEFAULT_TOLERANCE,
) -> List[ValidationError]:
    """
    Checks that the sum of line item amounts matches the invoice subtotal within tolerance:
      |sum(line_items.amount) - subtotal| <= tolerance (default 0.05)

    If subtotal is None, checks against invoice.total if tax is explicitly zero.
    If line items have missing amount but valid quantity and unit_price, computes quantity * unit_price.
    If line items have indeterminate amounts, emits a WARNING and avoids false arithmetic success.
    """
    issues: List[ValidationError] = []
    tol = _coerce_tolerance(tolerance)

    if not invoice.line_items:
        if invoice.subtotal is not None or invoice.total is not None:
            issues.append(
                ValidationError(
                    rule_id=ValidationRuleId.MATH_LINE_ITEM_SUM.value,
                    field="line_items",
                    message="Invoice has no line items; itemized sum could not be verified against subtotal.",
                    severity=ValidationSeverity.WARNING,
                )
            )
        return issues

    computed_sum = Decimal("0.00")
    has_indeterminate_item = False

    for idx, item in enumerate(invoice.line_items):
        if item.amount is not None:
            computed_sum += item.amount
        elif item.quantity is not None and item.unit_price is not None:
            computed_sum += (item.quantity * item.unit_price)
        else:
            has_indeterminate_item = True
            issues.append(
                ValidationError(
                    rule_id=ValidationRuleId.MATH_LINE_ITEM_SUM.value,
                    field=f"line_items[{idx}]",
                    message=(
                        f"Line item {idx + 1} ('{item.description}') is missing both amount and unit price/quantity; "
                        "item sum is incomplete."
                    ),
                    severity=ValidationSeverity.WARNING,
                )
            )

    # Determine reference subtotal
    target_subtotal = invoice.subtotal
    target_field = "subtotal"

    if target_subtotal is None and invoice.total is not None and invoice.tax == Decimal("0.00"):
        target_subtotal = invoice.total
        target_field = "total"

    if target_subtotal is not None:
        if has_indeterminate_item:
            # If known items already exceed subtotal + tolerance, that's a definite error
            if computed_sum > target_subtotal + tol:
                diff = computed_sum - target_subtotal
                issues.append(
                    ValidationError(
                        rule_id=ValidationRuleId.MATH_LINE_ITEM_SUM.value,
                        field=target_field,
                        message=(
                            f"Known line items sum ({computed_sum}) exceeds stated {target_field} ({target_subtotal}) "
                            f"by {diff} (tolerance: {tol}), and some line item amounts are missing."
                        ),
                        severity=ValidationSeverity.ERROR,
                        expected=f"<= {target_subtotal}",
                        actual=str(computed_sum),
                        difference=diff,
                    )
                )
            else:
                # Incomplete line items cannot confirm equality; emit warning rather than false arithmetic success
                issues.append(
                    ValidationError(
                        rule_id=ValidationRuleId.MATH_LINE_ITEM_SUM.value,
                        field=target_field,
                        message=(
                            f"Line items sum ({computed_sum}) cannot definitively verify stated {target_field} ({target_subtotal}) "
                            "because one or more line items have indeterminate amounts."
                        ),
                        severity=ValidationSeverity.WARNING,
                        expected=str(target_subtotal),
                        actual=str(computed_sum),
                    )
                )
        else:
            # All line items have known amounts
            diff = abs(computed_sum - target_subtotal)
            if diff > tol:
                issues.append(
                    ValidationError(
                        rule_id=ValidationRuleId.MATH_LINE_ITEM_SUM.value,
                        field=target_field,
                        message=(
                            f"Line items sum ({computed_sum}) differs from stated {target_field} ({target_subtotal}) "
                            f"by {diff} (tolerance: {tol})."
                        ),
                        severity=ValidationSeverity.ERROR,
                        expected=str(computed_sum),
                        actual=str(target_subtotal),
                        difference=diff,
                    )
                )

    return issues


def verify_tax_addition(
    invoice: InvoiceExtraction,
    tolerance: Union[Decimal, float, str, int] = DEFAULT_TOLERANCE,
) -> List[ValidationError]:
    """
    Checks that subtotal + tax equals total within tolerance:
      |subtotal + tax - total| <= tolerance (default 0.05)

    Rules:
      - When tax is explicitly 0.00: verifies subtotal == total.
      - When tax is null/None: does NOT silently assume zero tax. If subtotal == total, flags a WARNING
        requiring operator review for tax exemption; if subtotal != total, flags an ERROR.
      - Tax cannot be negative (flags ERROR).
      - Tax cannot exceed total (flags ERROR).
      - If subtotal is missing, attempts inference from line items, or flags WARNING if unverifiable.
    """
    issues: List[ValidationError] = []
    tol = _coerce_tolerance(tolerance)

    subtotal = invoice.subtotal
    tax = invoice.tax
    total = invoice.total

    # If subtotal is missing but line items are present and complete, infer subtotal
    if subtotal is None and invoice.line_items:
        items_with_amount = [
            it.amount if it.amount is not None else (it.quantity * it.unit_price if it.quantity and it.unit_price else None)
            for it in invoice.line_items
        ]
        if all(a is not None for a in items_with_amount) and items_with_amount:
            subtotal = sum(items_with_amount)

    # Missing total is covered by missing critical fields check
    if total is None:
        return issues

    # Negative tax check
    if tax is not None and tax < Decimal("0.00"):
        issues.append(
            ValidationError(
                rule_id=ValidationRuleId.MATH_TAX_ADDITION.value,
                field="tax",
                message=f"Tax amount cannot be negative: {tax}.",
                severity=ValidationSeverity.ERROR,
                expected=">= 0.00",
                actual=str(tax),
            )
        )
        return issues

    # Tax cannot exceed total
    if tax is not None and tax > total:
        issues.append(
            ValidationError(
                rule_id=ValidationRuleId.MATH_TAX_ADDITION.value,
                field="tax",
                message=f"Tax amount ({tax}) exceeds final invoice total ({total}).",
                severity=ValidationSeverity.ERROR,
                expected=f"<= {total}",
                actual=str(tax),
                difference=tax - total,
            )
        )
        return issues

    # If subtotal is still missing, tax addition cannot be verified
    if subtotal is None:
        issues.append(
            ValidationError(
                rule_id=ValidationRuleId.MATH_TAX_ADDITION.value,
                field="subtotal",
                message="Subtotal is missing; tax addition check cannot be verified against total.",
                severity=ValidationSeverity.WARNING,
            )
        )
        return issues

    # When tax is null/unspecified: do not silently assume null means zero
    if tax is None:
        diff = abs(subtotal - total)
        if diff <= tol:
            issues.append(
                ValidationError(
                    rule_id=ValidationRuleId.MATH_TAX_ADDITION.value,
                    field="tax",
                    message=(
                        f"Tax is null/unspecified. Stated subtotal ({subtotal}) matches total ({total}), "
                        "but tax exemption requires operator review."
                    ),
                    severity=ValidationSeverity.WARNING,
                    expected="Declared tax or 0.00",
                    actual="null",
                    difference=diff,
                )
            )
        else:
            issues.append(
                ValidationError(
                    rule_id=ValidationRuleId.MATH_TAX_ADDITION.value,
                    field="tax",
                    message=(
                        f"Invoice total ({total}) does not equal subtotal ({subtotal}) and tax is null/unspecified "
                        f"(unaccounted difference: {diff}, tolerance: {tol})."
                    ),
                    severity=ValidationSeverity.ERROR,
                    expected=str(total - subtotal),
                    actual="null",
                    difference=diff,
                )
            )
        return issues

    # When tax is explicitly specified (including Decimal("0.00"))
    expected_total = subtotal + tax
    diff = abs(expected_total - total)
    if diff > tol:
        issues.append(
            ValidationError(
                rule_id=ValidationRuleId.MATH_TAX_ADDITION.value,
                field="total",
                message=(
                    f"Subtotal ({subtotal}) + tax ({tax}) = {expected_total}, which differs from total ({total}) "
                    f"by {diff} (tolerance: {tol})."
                ),
                severity=ValidationSeverity.ERROR,
                expected=str(expected_total),
                actual=str(total),
                difference=diff,
            )
        )

    return issues


def verify_line_item_calculations(
    invoice: InvoiceExtraction,
    tolerance: Union[Decimal, float, str, int] = DEFAULT_TOLERANCE,
) -> List[ValidationError]:
    """
    Checks that each item's quantity * unit_price matches its amount within tolerance:
      |quantity * unit_price - amount| <= tolerance (default 0.05)
    """
    issues: List[ValidationError] = []
    tol = _coerce_tolerance(tolerance)

    for idx, item in enumerate(invoice.line_items):
        if item.quantity is not None and item.unit_price is not None and item.amount is not None:
            expected_amount = item.quantity * item.unit_price
            diff = abs(expected_amount - item.amount)

            if diff > tol:
                issues.append(
                    ValidationError(
                        rule_id=ValidationRuleId.MATH_ITEM_CALCULATION.value,
                        field=f"line_items[{idx}].amount",
                        message=(
                            f"Line item {idx + 1} ('{item.description}') arithmetic error: "
                            f"quantity ({item.quantity}) * unit_price ({item.unit_price}) = {expected_amount}, "
                            f"which differs from stated amount ({item.amount}) by {diff}."
                        ),
                        severity=ValidationSeverity.ERROR,
                        expected=str(expected_amount),
                        actual=str(item.amount),
                        difference=diff,
                    )
                )

    return issues


def run_all_math_rules(
    invoice: InvoiceExtraction,
    tolerance: Union[Decimal, float, str, int] = DEFAULT_TOLERANCE,
) -> List[ValidationError]:
    """Runs all mathematical rules and returns all discovered errors and warnings."""
    all_issues: List[ValidationError] = []
    all_issues.extend(verify_line_item_calculations(invoice, tolerance=tolerance))
    all_issues.extend(verify_line_item_sum(invoice, tolerance=tolerance))
    all_issues.extend(verify_tax_addition(invoice, tolerance=tolerance))
    return all_issues
