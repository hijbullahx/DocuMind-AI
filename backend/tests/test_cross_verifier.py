"""
Comprehensive test suite for TASK-009: Deterministic Cross-Document Verification Engine.
Tests cross-document reconciliation across totals, subtotals, tax, currency, parties, references,
line items, PDF-PDF pairs, PDF-Excel/spreadsheet pairs, and status determination (VERIFIED, NEEDS_REVIEW, FAILED).
"""
from decimal import Decimal
import json
import pytest

from apps.extraction.schemas import InvoiceExtraction, LineItemExtraction
from apps.ingestion.base import DocumentExtractionResult, DocumentMetadata, ExtractionStatus, PageExtraction
from apps.validation import (
    CrossDocumentDiscrepancy,
    CrossDocumentVerifier,
    CrossVerificationResult,
    CrossVerificationRuleId,
    ValidationSeverity,
    ValidationStatus,
)


def make_invoice(
    invoice_number: str = "INV-2026-001",
    supplier_name: str = "Apex Industrial Supplies LLC",
    customer_name: str = "Omega Logistics Corp",
    total: Decimal = Decimal("1000.00"),
    subtotal: Decimal = Decimal("900.00"),
    tax: Decimal = Decimal("100.00"),
    currency: str = "USD",
    line_items: list = None,
) -> InvoiceExtraction:
    """Helper to build consistent invoice models for reconciliation testing."""
    if line_items is None:
        line_items = [
            LineItemExtraction(
                description="Heavy Duty Pressure Valve",
                quantity=Decimal("3"),
                unit_price=Decimal("200.00"),
                amount=Decimal("600.00"),
            ),
            LineItemExtraction(
                description="Standard Steel Flange Set",
                quantity=Decimal("3"),
                unit_price=Decimal("100.00"),
                amount=Decimal("300.00"),
            ),
        ]
    return InvoiceExtraction(
        invoice_number=invoice_number,
        invoice_date="2026-05-10",
        due_date="2026-06-10",
        supplier_name=supplier_name,
        customer_name=customer_name,
        subtotal=subtotal,
        tax=tax,
        total=total,
        currency=currency,
        line_items=line_items,
    )


# =========================================================================
# 1. Matching and Compatible Documents (VERIFIED)
# =========================================================================

class TestMatchingDocuments:
    """Tests where paired documents match and achieve VERIFIED status."""

    def test_identical_invoices_reconcile_successfully(self):
        verifier = CrossDocumentVerifier()
        doc_a = make_invoice()
        doc_b = make_invoice()

        result = verifier.reconcile(doc_a, doc_b, doc_a_id="invoice_pdf", doc_b_id="po_pdf")

        assert result.status == ValidationStatus.VERIFIED
        assert result.is_reconciled is True
        assert len(result.discrepancies) == 0
        assert len(result.warnings) == 0
        assert result.matched_items_count == 2
        assert result.unmatched_items_count == 0
        assert "successfully verified" in result.summary.lower()

    def test_total_within_tolerance_reconciles_successfully(self):
        verifier = CrossDocumentVerifier(default_tolerance=Decimal("0.05"))
        # doc_a total is 1000.00, doc_b total is 1000.04 (diff = 0.04 <= 0.05)
        doc_a = make_invoice(total=Decimal("1000.00"))
        doc_b = make_invoice(total=Decimal("1000.04"))

        result = verifier.reconcile(doc_a, doc_b)

        assert result.status == ValidationStatus.VERIFIED
        assert result.is_reconciled is True
        assert len(result.discrepancies) == 0

    def test_currency_symbol_to_code_normalization_matches(self):
        verifier = CrossDocumentVerifier()
        doc_a = make_invoice(currency="$")
        doc_b = make_invoice(currency="USD")

        result = verifier.reconcile(doc_a, doc_b)

        assert result.status == ValidationStatus.VERIFIED
        assert result.is_reconciled is True

    def test_supplier_name_normalization_matches(self):
        verifier = CrossDocumentVerifier()
        doc_a = make_invoice(supplier_name="Apex Industrial Supplies LLC.")
        doc_b = make_invoice(supplier_name="  apex industrial supplies llc  ")

        result = verifier.reconcile(doc_a, doc_b)

        assert result.status == ValidationStatus.VERIFIED
        assert result.is_reconciled is True

    def test_fuzzy_item_description_matches(self):
        verifier = CrossDocumentVerifier()
        # Slight variation in item wording (punctuation and casing)
        doc_a = make_invoice(
            line_items=[
                LineItemExtraction(
                    description="Heavy Duty Pressure Valve (Model A)",
                    quantity=Decimal("1"),
                    unit_price=Decimal("500.00"),
                    amount=Decimal("500.00"),
                )
            ],
            total=Decimal("500.00"),
            subtotal=Decimal("500.00"),
            tax=Decimal("0.00"),
        )
        doc_b = make_invoice(
            line_items=[
                LineItemExtraction(
                    description="Heavy Duty Pressure Valve Model A",
                    quantity=Decimal("1"),
                    unit_price=Decimal("500.00"),
                    amount=Decimal("500.00"),
                )
            ],
            total=Decimal("500.00"),
            subtotal=Decimal("500.00"),
            tax=Decimal("0.00"),
        )

        result = verifier.reconcile(doc_a, doc_b)

        assert result.status == ValidationStatus.VERIFIED
        assert result.is_reconciled is True
        assert result.matched_items_count == 1
        assert result.unmatched_items_count == 0


# =========================================================================
# 2. Genuine Financial Discrepancies (FAILED)
# =========================================================================

class TestFinancialDiscrepancies:
    """Tests where numerical or financial conflicts cause reconciliation to fail."""

    def test_total_amount_mismatch_fails(self):
        verifier = CrossDocumentVerifier()
        doc_a = make_invoice(total=Decimal("1000.00"))
        doc_b = make_invoice(total=Decimal("950.00"))  # diff 50.00 > 0.05

        result = verifier.reconcile(doc_a, doc_b, doc_a_id="invoice", doc_b_id="po")

        assert result.status == ValidationStatus.FAILED
        assert result.is_reconciled is False
        assert len(result.discrepancies) == 1
        err = result.discrepancies[0]
        assert err.rule_id == CrossVerificationRuleId.CROSS_TOTAL_MISMATCH.value
        assert err.field == "total"
        assert err.difference == Decimal("50.00")
        assert "invoice" in err.message and "po" in err.message

    def test_subtotal_mismatch_fails(self):
        verifier = CrossDocumentVerifier()
        doc_a = make_invoice(subtotal=Decimal("900.00"))
        doc_b = make_invoice(subtotal=Decimal("800.00"))

        result = verifier.reconcile(doc_a, doc_b)

        assert result.status == ValidationStatus.FAILED
        assert any(d.rule_id == CrossVerificationRuleId.CROSS_SUBTOTAL_MISMATCH.value for d in result.discrepancies)

    def test_tax_mismatch_fails(self):
        verifier = CrossDocumentVerifier()
        doc_a = make_invoice(tax=Decimal("100.00"))
        doc_b = make_invoice(tax=Decimal("120.00"))

        result = verifier.reconcile(doc_a, doc_b)

        assert result.status == ValidationStatus.FAILED
        assert any(d.rule_id == CrossVerificationRuleId.CROSS_TAX_MISMATCH.value for d in result.discrepancies)

    def test_currency_mismatch_fails(self):
        verifier = CrossDocumentVerifier()
        doc_a = make_invoice(currency="USD")
        doc_b = make_invoice(currency="EUR")

        result = verifier.reconcile(doc_a, doc_b)

        assert result.status == ValidationStatus.FAILED
        assert any(d.rule_id == CrossVerificationRuleId.CROSS_CURRENCY_MISMATCH.value for d in result.discrepancies)

    def test_supplier_name_mismatch_fails(self):
        verifier = CrossDocumentVerifier()
        doc_a = make_invoice(supplier_name="Acme Corp")
        doc_b = make_invoice(supplier_name="Beta Logistics")

        result = verifier.reconcile(doc_a, doc_b)

        assert result.status == ValidationStatus.FAILED
        assert any(d.rule_id == CrossVerificationRuleId.CROSS_SUPPLIER_MISMATCH.value for d in result.discrepancies)


# =========================================================================
# 3. Line Item Discrepancies and Quantity/Price Overcharges
# =========================================================================

class TestLineItemReconciliation:
    """Tests item-level comparisons including quantity, unit price, and unmatched items."""

    def test_item_quantity_mismatch_fails(self):
        verifier = CrossDocumentVerifier()
        # PO has quantity 3; Invoice billed quantity 5
        doc_a = make_invoice(
            line_items=[
                LineItemExtraction(description="Valve", quantity=Decimal("3"), unit_price=Decimal("100.00"), amount=Decimal("300.00"))
            ]
        )
        doc_b = make_invoice(
            line_items=[
                LineItemExtraction(description="Valve", quantity=Decimal("5"), unit_price=Decimal("100.00"), amount=Decimal("500.00"))
            ],
            total=Decimal("500.00"),
            subtotal=Decimal("500.00"),
        )

        result = verifier.reconcile(doc_a, doc_b)

        assert result.status == ValidationStatus.FAILED
        assert any(d.rule_id == CrossVerificationRuleId.CROSS_ITEM_MISMATCH.value and "quantity" in d.field for d in result.discrepancies)

    def test_item_unit_price_mismatch_fails(self):
        verifier = CrossDocumentVerifier()
        # Agreed PO unit price 100.00; Invoice billed 150.00
        doc_a = make_invoice(
            line_items=[
                LineItemExtraction(description="Valve", quantity=Decimal("1"), unit_price=Decimal("100.00"), amount=Decimal("100.00"))
            ],
            total=Decimal("100.00"),
            subtotal=Decimal("100.00"),
        )
        doc_b = make_invoice(
            line_items=[
                LineItemExtraction(description="Valve", quantity=Decimal("1"), unit_price=Decimal("150.00"), amount=Decimal("150.00"))
            ],
            total=Decimal("150.00"),
            subtotal=Decimal("150.00"),
        )

        result = verifier.reconcile(doc_a, doc_b)

        assert result.status == ValidationStatus.FAILED
        assert any(d.rule_id == CrossVerificationRuleId.CROSS_ITEM_MISMATCH.value and "unit_price" in d.field for d in result.discrepancies)

    def test_unmatched_extra_line_item_triggers_warning_needs_review(self):
        verifier = CrossDocumentVerifier()
        # doc_a has 1 item; doc_b has that item plus an extra unauthorized item
        # totals match for the test to isolate the line item warning
        item_1 = LineItemExtraction(description="Approved Service", quantity=Decimal("1"), unit_price=Decimal("500.00"), amount=Decimal("500.00"))
        item_2 = LineItemExtraction(description="Unapproved Extra Item", quantity=Decimal("1"), unit_price=Decimal("100.00"), amount=Decimal("100.00"))

        doc_a = make_invoice(line_items=[item_1], total=Decimal("600.00"), subtotal=Decimal("600.00"))
        doc_b = make_invoice(line_items=[item_1, item_2], total=Decimal("600.00"), subtotal=Decimal("600.00"))

        result = verifier.reconcile(doc_a, doc_b)

        assert result.status == ValidationStatus.NEEDS_REVIEW
        assert result.is_reconciled is False
        assert len(result.discrepancies) == 0
        assert len(result.warnings) >= 1
        assert any(w.rule_id == CrossVerificationRuleId.CROSS_UNMATCHED_ITEM.value for w in result.warnings)
        assert result.matched_items_count == 1
        assert result.unmatched_items_count == 1


# =========================================================================
# 4. Conservative Missing/Null Field Handling
# =========================================================================

class TestConservativeMissingData:
    """Verifies that missing data is handled conservatively and does not produce false mismatches."""

    def test_missing_total_in_one_document_warns_rather_than_false_mismatch_error(self):
        verifier = CrossDocumentVerifier()
        # doc_a has total; doc_b has total=None
        doc_a = make_invoice(total=Decimal("1000.00"))
        doc_b = make_invoice(total=None)

        result = verifier.reconcile(doc_a, doc_b)

        # Must not be FAILED (not a proven mismatch)
        assert result.status == ValidationStatus.NEEDS_REVIEW
        assert result.is_reconciled is False
        assert len(result.discrepancies) == 0
        assert any(w.rule_id == CrossVerificationRuleId.CROSS_INCOMPLETE_COMPARISON.value for w in result.warnings)

    def test_missing_supplier_in_one_document_does_not_fail(self):
        verifier = CrossDocumentVerifier()
        doc_a = make_invoice(supplier_name="Acme Corp")
        doc_b = make_invoice(supplier_name=None)

        result = verifier.reconcile(doc_a, doc_b)

        # Missing supplier in doc_b is not treated as a mismatch
        assert result.status == ValidationStatus.VERIFIED
        assert result.is_reconciled is True

    def test_missing_subtotal_and_tax_in_both_passes_if_totals_match(self):
        verifier = CrossDocumentVerifier()
        doc_a = make_invoice(subtotal=None, tax=None)
        doc_b = make_invoice(subtotal=None, tax=None)

        result = verifier.reconcile(doc_a, doc_b)

        assert result.status == ValidationStatus.VERIFIED
        assert result.is_reconciled is True


# =========================================================================
# 5. Reference Number Matching Modes (Strict vs Permissive)
# =========================================================================

class TestReferenceNumberMatching:
    """Tests invoice/PO reference matching in strict and non-strict modes."""

    def test_reference_mismatch_non_strict_mode_warns_for_review(self):
        # Default mode (strict_reference_matching=False) flags warning for PO-Invoice reference check
        verifier = CrossDocumentVerifier(strict_reference_matching=False)
        doc_a = make_invoice(invoice_number="INV-2026-001")
        doc_b = make_invoice(invoice_number="PO-9999")

        result = verifier.reconcile(doc_a, doc_b)

        assert result.status == ValidationStatus.NEEDS_REVIEW
        assert result.is_reconciled is False
        assert len(result.discrepancies) == 0
        assert any(w.rule_id == CrossVerificationRuleId.CROSS_REFERENCE_MISMATCH.value for w in result.warnings)

    def test_reference_mismatch_strict_mode_fails(self):
        # Strict mode requires exact reference match (e.g. comparing two copies of an invoice)
        verifier = CrossDocumentVerifier(strict_reference_matching=True)
        doc_a = make_invoice(invoice_number="INV-2026-001")
        doc_b = make_invoice(invoice_number="INV-2026-002")

        result = verifier.reconcile(doc_a, doc_b)

        assert result.status == ValidationStatus.FAILED
        assert result.is_reconciled is False
        assert any(d.rule_id == CrossVerificationRuleId.CROSS_REFERENCE_MISMATCH.value for d in result.discrepancies)


# =========================================================================
# 6. PDF-Excel & Tabular Spreadsheet Reconciliation
# =========================================================================

class TestSpreadsheetAndTabularReconciliation:
    """Tests reconciling an InvoiceExtraction against tabular rows or DocumentExtractionResult."""

    def test_reconcile_with_list_of_item_dicts(self):
        verifier = CrossDocumentVerifier()
        invoice = make_invoice(
            total=Decimal("900.00"),
            subtotal=Decimal("900.00"),
            tax=Decimal("0.00"),
        )
        # Spreadsheet rows as a list of item dictionaries
        spreadsheet_rows = [
            {"description": "Heavy Duty Pressure Valve", "quantity": 3, "unit_price": 200.00, "amount": 600.00},
            {"description": "Standard Steel Flange Set", "quantity": 3, "unit_price": 100.00, "amount": 300.00},
        ]

        result = verifier.reconcile(invoice, spreadsheet_rows, doc_a_id="invoice_pdf", doc_b_id="excel_sheet")

        assert result.status == ValidationStatus.VERIFIED
        assert result.is_reconciled is True
        assert result.matched_items_count == 2

    def test_reconcile_with_document_extraction_result_tables(self):
        verifier = CrossDocumentVerifier()
        invoice = make_invoice(
            total=Decimal("700.00"),
            subtotal=Decimal("700.00"),
            tax=Decimal("0.00"),
            line_items=[
                LineItemExtraction(description="Widget X", quantity=Decimal("2"), unit_price=Decimal("200.00"), amount=Decimal("400.00")),
                LineItemExtraction(description="Widget Y", quantity=Decimal("3"), unit_price=Decimal("100.00"), amount=Decimal("300.00")),
            ],
        )

        table_data = [
            ["Item Description", "Quantity", "Unit Price", "Total Amount"],
            ["Widget X", "2", "200.00", "400.00"],
            ["Widget Y", "3", "100.00", "300.00"],
        ]
        doc_result = DocumentExtractionResult(
            filename="purchase_order.xlsx",
            file_type="xlsx",
            status=ExtractionStatus.SUCCESS,
            metadata=DocumentMetadata(page_count=1),
            pages=[PageExtraction(page_number=1, tables=[table_data])],
        )

        result = verifier.reconcile(invoice, doc_result, doc_a_id="invoice_pdf", doc_b_id="po_excel")

        assert result.status == ValidationStatus.VERIFIED
        assert result.is_reconciled is True
        assert result.matched_items_count == 2

    def test_reconcile_with_raw_json_string(self):
        verifier = CrossDocumentVerifier()
        invoice = make_invoice()
        raw_json = json.dumps(invoice.model_dump(mode="json"))

        result = verifier.reconcile(invoice, raw_json)

        assert result.status == ValidationStatus.VERIFIED
        assert result.is_reconciled is True


# =========================================================================
# 7. Error Handling, Deduplication, and Serialization
# =========================================================================

class TestErrorHandlingAndSerialization:
    """Tests malformed input recovery, duplicate suppression, and JSON serialization."""

    def test_malformed_input_returns_failed_result_without_crash(self):
        verifier = CrossDocumentVerifier()
        invoice = make_invoice()

        result = verifier.reconcile(invoice, "{bad json:")

        assert result.status == ValidationStatus.FAILED
        assert result.is_reconciled is False
        assert len(result.discrepancies) == 1
        assert result.discrepancies[0].rule_id == CrossVerificationRuleId.CROSS_INCOMPATIBLE_DOCUMENT.value

    def test_unsupported_type_returns_failed_result(self):
        verifier = CrossDocumentVerifier()
        invoice = make_invoice()

        result = verifier.reconcile(invoice, 99999)

        assert result.status == ValidationStatus.FAILED
        assert result.is_reconciled is False
        assert result.discrepancies[0].rule_id == CrossVerificationRuleId.CROSS_INCOMPATIBLE_DOCUMENT.value

    def test_duplicate_discrepancy_suppression(self):
        verifier = CrossDocumentVerifier()
        doc_a = make_invoice(total=Decimal("1000.00"))
        doc_b = make_invoice(total=Decimal("900.00"))

        result = verifier.reconcile(doc_a, doc_b)

        # Total discrepancy must only be recorded once
        total_errs = [d for d in result.discrepancies if d.field == "total"]
        assert len(total_errs) == 1

    def test_result_to_dict_serialization_purity(self):
        verifier = CrossDocumentVerifier()
        doc_a = make_invoice(total=Decimal("1000.00"))
        doc_b = make_invoice(total=Decimal("950.00"))

        result = verifier.reconcile(doc_a, doc_b, doc_a_id="INV-001", doc_b_id="PO-001")
        res_dict = result.to_dict()

        assert res_dict["status"] == "FAILED"
        assert res_dict["is_reconciled"] is False
        assert res_dict["doc_a_id"] == "INV-001"
        assert res_dict["doc_b_id"] == "PO-001"
        assert len(res_dict["discrepancies"]) == 1
        # Roundtrip JSON serialization check
        serialized = json.dumps(res_dict)
        deserialized = json.loads(serialized)
        assert deserialized["status"] == "FAILED"


# =========================================================================
# 8. Advanced Edge Cases, Boundary Precision, and Line-Item Ranking
# =========================================================================

class TestAdvancedReconciliationEdgeCases:
    """Verifies edge cases including candidate matching order, identical descriptions, and boundary tolerances."""

    def test_line_item_matching_prefers_exact_over_partial_regardless_of_order(self):
        verifier = CrossDocumentVerifier(min_item_similarity=0.50)
        # Doc A: item 0 has description "Software License Pro", item 1 has description "Software License"
        # Doc B: item 0 has description "Software License", item 1 has description "Software License Pro"
        item_a0 = LineItemExtraction(description="Software License Pro", quantity=Decimal("1"), unit_price=Decimal("200.00"), amount=Decimal("200.00"))
        item_a1 = LineItemExtraction(description="Software License", quantity=Decimal("1"), unit_price=Decimal("100.00"), amount=Decimal("100.00"))
        item_b0 = LineItemExtraction(description="Software License", quantity=Decimal("1"), unit_price=Decimal("100.00"), amount=Decimal("100.00"))
        item_b1 = LineItemExtraction(description="Software License Pro", quantity=Decimal("1"), unit_price=Decimal("200.00"), amount=Decimal("200.00"))

        doc_a = make_invoice(line_items=[item_a0, item_a1], total=Decimal("300.00"), subtotal=Decimal("300.00"), tax=Decimal("0.00"))
        doc_b = make_invoice(line_items=[item_b0, item_b1], total=Decimal("300.00"), subtotal=Decimal("300.00"), tax=Decimal("0.00"))

        result = verifier.reconcile(doc_a, doc_b)

        assert result.status == ValidationStatus.VERIFIED
        assert result.is_reconciled is True
        assert result.matched_items_count == 2
        assert result.unmatched_items_count == 0
        assert len(result.discrepancies) == 0

    def test_line_item_matching_order_independence(self):
        verifier = CrossDocumentVerifier()
        item_1 = LineItemExtraction(description="Item Alpha", quantity=Decimal("2"), unit_price=Decimal("50.00"), amount=Decimal("100.00"))
        item_2 = LineItemExtraction(description="Item Beta", quantity=Decimal("4"), unit_price=Decimal("25.00"), amount=Decimal("100.00"))

        doc_a = make_invoice(line_items=[item_1, item_2], total=Decimal("200.00"), subtotal=Decimal("200.00"), tax=Decimal("0.00"))
        # doc_b has reversed order
        doc_b = make_invoice(line_items=[item_2, item_1], total=Decimal("200.00"), subtotal=Decimal("200.00"), tax=Decimal("0.00"))

        result = verifier.reconcile(doc_a, doc_b)

        assert result.status == ValidationStatus.VERIFIED
        assert result.matched_items_count == 2
        assert result.unmatched_items_count == 0

    def test_multiple_identical_descriptions_distinct_discrepancies(self):
        verifier = CrossDocumentVerifier()
        # Two distinct rows of "Standard Widget" with different quantities and prices
        doc_a = make_invoice(
            line_items=[
                LineItemExtraction(description="Standard Widget", quantity=Decimal("2"), unit_price=Decimal("50.00"), amount=Decimal("100.00")),
                LineItemExtraction(description="Standard Widget", quantity=Decimal("4"), unit_price=Decimal("50.00"), amount=Decimal("200.00")),
            ],
            total=Decimal("300.00"),
            subtotal=Decimal("300.00"),
            tax=Decimal("0.00"),
        )
        doc_b = make_invoice(
            line_items=[
                LineItemExtraction(description="Standard Widget", quantity=Decimal("3"), unit_price=Decimal("50.00"), amount=Decimal("150.00")),
                LineItemExtraction(description="Standard Widget", quantity=Decimal("5"), unit_price=Decimal("50.00"), amount=Decimal("250.00")),
            ],
            total=Decimal("400.00"),
            subtotal=Decimal("400.00"),
            tax=Decimal("0.00"),
        )

        result = verifier.reconcile(doc_a, doc_b)

        assert result.status == ValidationStatus.FAILED
        item_errs = [d for d in result.discrepancies if d.rule_id == CrossVerificationRuleId.CROSS_ITEM_MISMATCH.value]
        # Both line items should have errors reported independently with their respective indices
        fields = {d.field for d in item_errs}
        assert any("line_items[0]" in f for f in fields)
        assert any("line_items[1]" in f for f in fields)

    def test_multiple_unmatched_items_with_same_description_not_suppressed(self):
        verifier = CrossDocumentVerifier()
        # Doc A has two identical unlisted items that Doc B doesn't have
        doc_a = make_invoice(
            line_items=[
                LineItemExtraction(description="Spare Part Kit", quantity=Decimal("1"), unit_price=Decimal("50.00"), amount=Decimal("50.00")),
                LineItemExtraction(description="Spare Part Kit", quantity=Decimal("1"), unit_price=Decimal("50.00"), amount=Decimal("50.00")),
            ],
            total=Decimal("100.00"),
            subtotal=Decimal("100.00"),
            tax=Decimal("0.00"),
        )
        doc_b = make_invoice(line_items=[], total=Decimal("100.00"), subtotal=Decimal("100.00"), tax=Decimal("0.00"))

        result = verifier.reconcile(doc_a, doc_b)

        assert result.status == ValidationStatus.NEEDS_REVIEW
        unmatched_warnings = [w for w in result.warnings if w.rule_id == CrossVerificationRuleId.CROSS_UNMATCHED_ITEM.value]
        assert len(unmatched_warnings) == 2
        assert unmatched_warnings[0].field == "line_items[0]"
        assert unmatched_warnings[1].field == "line_items[1]"

    def test_exact_tolerance_boundary_precision(self):
        verifier = CrossDocumentVerifier(default_tolerance=Decimal("0.05"))
        # Exactly 0.05 diff passes
        doc_a = make_invoice(total=Decimal("100.00"))
        doc_b = make_invoice(total=Decimal("100.05"))
        result_pass = verifier.reconcile(doc_a, doc_b)
        assert result_pass.status == ValidationStatus.VERIFIED

        # 0.051 diff fails
        doc_c = make_invoice(total=Decimal("100.051"))
        result_fail = verifier.reconcile(doc_a, doc_c)
        assert result_fail.status == ValidationStatus.FAILED
        assert any(d.rule_id == CrossVerificationRuleId.CROSS_TOTAL_MISMATCH.value for d in result_fail.discrepancies)

    def test_currency_conflict_overrides_numeric_equality(self):
        verifier = CrossDocumentVerifier()
        # Both total 1000.00, but USD vs EUR
        doc_a = make_invoice(total=Decimal("1000.00"), currency="USD")
        doc_b = make_invoice(total=Decimal("1000.00"), currency="EUR")

        result = verifier.reconcile(doc_a, doc_b)

        assert result.status == ValidationStatus.FAILED
        assert any(d.rule_id == CrossVerificationRuleId.CROSS_CURRENCY_MISMATCH.value for d in result.discrepancies)

    def test_customer_mismatch_produces_warning_needs_review(self):
        verifier = CrossDocumentVerifier()
        doc_a = make_invoice(customer_name="Alpha Healthcare Inc.")
        doc_b = make_invoice(customer_name="Beta Healthcare Ltd.")

        result = verifier.reconcile(doc_a, doc_b)

        assert result.status == ValidationStatus.NEEDS_REVIEW
        assert result.is_reconciled is False
        assert any(w.rule_id == CrossVerificationRuleId.CROSS_CUSTOMER_MISMATCH.value for w in result.warnings)


