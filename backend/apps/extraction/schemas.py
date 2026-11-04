"""
Pydantic Schemas for Structured Invoice Extraction.
Defines InvoiceExtraction and LineItemExtraction with strict field validation,
provenance evidence mapping, and zero-hallucination null enforcement.
"""
from decimal import Decimal, InvalidOperation
import json
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class ExtractionSchemaError(ValueError):
    """Raised when raw model output cannot be parsed or fails schema validation."""
    pass


def _clean_decimal_str(v: Any) -> Optional[Decimal]:
    """
    Cleans and converts raw numeric inputs into Python Decimal.
    Accepted formats:
      - Integers, floats, and Decimals (non-negative, non-NaN, non-Infinite)
      - Standard integer string: "1250"
      - Standard decimal string: "1250.50", "0.75"
      - Standard thousands-grouped string: "1,250", "1,250.50", "12,345,678.90"
      - Strings with a single leading or trailing currency symbol: "$1,250.50", "1250.50 €", "£150"
      - Null/missing representations: None, "", "null", "none", "n/a", "na", "-", "unknown" -> returns None

    Rejects:
      - Negative numbers: "-150.00", -50 (standard payable invoices only; credit notes / negative debit adjustments are intentionally unsupported by this schema)
      - Ambiguous European decimal comma: "1250,50", "1.250,50" (intentionally rejected as ambiguous to prevent silent 100x calculation corruption)
      - Ambiguous or malformed comma grouping: "1,2", "1,25", "1,2,3", ",100", "100,", "1,,000"
      - Strings with multiple decimal points: "1.2.3"
      - Strings with multiple or conflicting currency symbols: "$100 €", "$$50"
      - Non-numeric text: "Ten Dollars"
    """
    if v is None:
        return None

    if isinstance(v, (int, float)):
        dec = Decimal(str(v))
        if dec.is_nan() or dec.is_infinite():
            raise ValueError(f"Financial amounts cannot be NaN or Infinite: {v}")
        if dec < 0:
            raise ValueError(f"Financial amounts cannot be negative: {v}")
        return dec

    if isinstance(v, Decimal):
        if v.is_nan() or v.is_infinite():
            raise ValueError(f"Financial amounts cannot be NaN or Infinite: {v}")
        if v < 0:
            raise ValueError(f"Financial amounts cannot be negative: {v}")
        return v

    if isinstance(v, str):
        cleaned = v.strip()
        if not cleaned or cleaned.lower() in ("null", "none", "n/a", "na", "-", "unknown"):
            return None

        # Detect currency symbols
        symbols = re.findall(r"[\$€£¥₹]", cleaned)
        if len(symbols) > 1:
            raise ValueError(f"Cannot parse '{v}' into decimal: multiple or conflicting currency symbols detected")

        # Strip the single currency symbol if present
        s_no_curr = re.sub(r"[\$€£¥₹]", "", cleaned).strip()

        # Reject negative indicator '-' anywhere
        if "-" in s_no_curr:
            raise ValueError(f"Financial amounts cannot be negative: {v}")

        # Reject any characters outside digits, commas, dots, and optional leading '+'
        if re.search(r"[^\d.,+]", s_no_curr):
            raise ValueError(f"Cannot parse '{v}' into a valid decimal number")

        # Strip optional leading '+'
        if s_no_curr.startswith("+"):
            s_no_curr = s_no_curr[1:].strip()

        if not s_no_curr:
            raise ValueError(f"Cannot parse '{v}' into a valid decimal number")

        # Comma handling
        if "," in s_no_curr:
            # Enforce standard US/UK thousands grouping: 1-3 digits followed by groups of ,3digits
            if not re.match(r"^\d{1,3}(,\d{3})+(\.\d+)?$", s_no_curr):
                raise ValueError(
                    f"Cannot parse '{v}' into a valid decimal number: ambiguous or invalid comma grouping"
                )
            s_clean = s_no_curr.replace(",", "")
        else:
            # Plain integer or decimal
            if not re.match(r"^\d+(\.\d+)?$", s_no_curr):
                raise ValueError(f"Cannot parse '{v}' into a valid decimal number")
            s_clean = s_no_curr

        try:
            dec = Decimal(s_clean)
            if dec < 0:
                raise ValueError(f"Financial amounts cannot be negative: {v}")
            return dec
        except InvalidOperation:
            raise ValueError(f"Cannot parse '{v}' into a valid decimal number")

    raise ValueError(f"Unsupported numeric type: {type(v)}")


# Alias for backward compatibility
_clean_numeric_input = _clean_decimal_str


class LineItemExtraction(BaseModel):
    """
    Itemized product or service row extracted from an invoice.
    All numeric fields default to None if absent in source text.
    """
    description: str = Field(
        ...,
        description="Verbatim description of the product or service. Cannot be empty."
    )
    quantity: Optional[Decimal] = Field(
        default=None,
        description="Billed quantity. null if not explicitly listed."
    )
    unit_price: Optional[Decimal] = Field(
        default=None,
        description="Unit price per item. null if not explicitly listed."
    )
    amount: Optional[Decimal] = Field(
        default=None,
        description="Total line amount (quantity * unit_price or stated line total). null if not listed."
    )

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned or cleaned.lower() in ("null", "none", "n/a", "na", "-", "unknown"):
            raise ValueError("Line item description cannot be empty or null")
        return cleaned

    @field_validator("quantity", "unit_price", "amount", mode="before")
    @classmethod
    def clean_numbers(cls, v: Any) -> Optional[Decimal]:
        return _clean_decimal_str(v)


class InvoiceExtraction(BaseModel):
    """
    Structured invoice extraction schema with strict null enforcement.
    Missing fields must be explicitly set to None (null in JSON).
    """
    invoice_number: Optional[str] = Field(
        default=None,
        description="Unique identifier / invoice number. null if not present."
    )
    invoice_date: Optional[str] = Field(
        default=None,
        description="Issue date (preferably YYYY-MM-DD or verbatim). null if not present."
    )
    due_date: Optional[str] = Field(
        default=None,
        description="Payment due date. null if not present."
    )
    supplier_name: Optional[str] = Field(
        default=None,
        description="Legal entity name of the supplier/vendor. null if not present."
    )
    supplier_address: Optional[str] = Field(
        default=None,
        description="Physical or mailing address of the supplier. null if not present."
    )
    customer_name: Optional[str] = Field(
        default=None,
        description="Name of the customer / bill-to recipient. null if not present."
    )
    customer_address: Optional[str] = Field(
        default=None,
        description="Address of the customer / bill-to recipient. null if not present."
    )
    subtotal: Optional[Decimal] = Field(
        default=None,
        description="Net total amount before tax. null if not explicitly listed."
    )
    tax: Optional[Decimal] = Field(
        default=None,
        description="Total tax / VAT / GST amount. null if not explicitly listed."
    )
    total: Optional[Decimal] = Field(
        default=None,
        description="Final gross total payable amount. null if not explicitly listed."
    )
    currency: Optional[str] = Field(
        default=None,
        description="Currency code or symbol (e.g. USD, EUR, GBP, $, €). null if not present."
    )
    line_items: List[LineItemExtraction] = Field(
        default_factory=list,
        description="List of itemized products or services. Empty list if none present."
    )
    raw_text_evidence: Dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Verbatim grounding quotes from document text claimed by extraction model. "
            "Note: Represents model-supplied provenance claims, not independently verified ground truth."
        )
    )

    @field_validator(
        "invoice_number",
        "invoice_date",
        "due_date",
        "supplier_name",
        "supplier_address",
        "customer_name",
        "customer_address",
        "currency",
        mode="before",
    )
    @classmethod
    def clean_text_fields(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        cleaned = str(v).strip()
        if not cleaned or cleaned.lower() in ("null", "none", "n/a", "na", "-", "unknown"):
            return None
        return cleaned

    @field_validator("subtotal", "tax", "total", mode="before")
    @classmethod
    def clean_totals(cls, v: Any) -> Optional[Decimal]:
        return _clean_decimal_str(v)

    @field_validator("line_items", mode="before")
    @classmethod
    def clean_line_items(cls, v: Any) -> List[Any]:
        if v is None or v == "" or v == "null":
            return []
        if isinstance(v, list):
            return v
        raise ValueError(f"Expected list for line_items, got {type(v).__name__}")

    @field_validator("raw_text_evidence", mode="before")
    @classmethod
    def clean_evidence(cls, v: Any) -> Dict[str, str]:
        if v is None or v == "" or v == "null":
            return {}
        if isinstance(v, dict):
            return {str(k): str(val) for k, val in v.items() if val is not None}
        raise ValueError(f"Expected dict for raw_text_evidence, got {type(v).__name__}")

    @classmethod
    def from_raw_json(cls, raw_text: str) -> "InvoiceExtraction":
        """
        Parses and validates a raw model completion string into an InvoiceExtraction.
        - Strips markdown code blocks (```json ... ```)
        - Finds and parses JSON object
        - Raises ExtractionSchemaError on malformed JSON or schema violations
        """
        if not raw_text or not raw_text.strip():
            raise ExtractionSchemaError("Empty or whitespace-only model completion")

        clean_text = raw_text.strip()

        # Strip markdown ```json code blocks if present
        if "```" in clean_text:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean_text)
            if match:
                clean_text = match.group(1).strip()

        # Parse JSON
        try:
            data = json.loads(clean_text)
        except json.JSONDecodeError as e:
            raise ExtractionSchemaError(f"Malformed JSON from extraction model: {e}") from e

        if not isinstance(data, dict):
            raise ExtractionSchemaError(f"Expected JSON object (dict), received: {type(data).__name__}")

        # Validate with Pydantic
        try:
            return cls.model_validate(data)
        except Exception as e:
            raise ExtractionSchemaError(f"Schema validation failure: {e}") from e
