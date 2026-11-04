# Database Schema & Entity Design
**DocuMind-AI: Enterprise Document Intelligence & Financial Validation System**

---

## 1. Relational Entity-Relationship Model

The system utilizes a relational schema engineered to store documents, extraction results, detailed line items, automated validation logs, and complete audit history.

```text
┌───────────────────────┐         ┌───────────────────────┐
│       documents       │1       1│   invoice_extractions │
├───────────────────────┤◄────────┼───────────────────────┤
│ id (UUID, PK)         │         │ id (UUID, PK)         │
│ filename (VARCHAR)    │         │ document_id (FK)      │
│ file_type (VARCHAR)   │         │ invoice_number (STR)  │
│ file_size (INT)       │         │ invoice_date (DATE)   │
│ file_path (VARCHAR)   │         │ supplier_name (STR)   │
│ status (ENUM)         │         │ customer_name (STR)   │
│ raw_text (TEXT)       │         │ subtotal (DECIMAL)    │
│ embedding (VECTOR)    │         │ tax (DECIMAL)         │
│ created_at (TIMESTAMP)│         │ total (DECIMAL)       │
│ updated_at (TIMESTAMP)│         │ currency (VARCHAR)    │
└───────────┬───────────┘         │ confidence_score(FLT) │
            │                     └───────────┬───────────┘
            │1                                │1
            │                                 │
            │*                                │*
┌───────────▼───────────┐         ┌───────────▼───────────┐
│   validation_errors   │         │    invoice_items      │
├───────────────────────┤         ├───────────────────────┤
│ id (UUID, PK)         │         │ id (UUID, PK)         │
│ document_id (FK)      │         │ extraction_id (FK)    │
│ rule_code (VARCHAR)   │         │ description (VARCHAR) │
│ severity (ENUM)       │         │ quantity (DECIMAL)    │
│ field_name (VARCHAR)  │         │ unit_price (DECIMAL)  │
│ error_message (TEXT)  │         │ amount (DECIMAL)      │
│ created_at (TIMESTAMP)│         └───────────────────────┘
└───────────────────────┘
            │1
            │
            │*
┌───────────▼───────────┐
│     audit_logs        │
├───────────────────────┤
│ id (UUID, PK)         │
│ document_id (FK)      │
│ changed_field (STR)   │
│ old_value (TEXT)      │
│ new_value (TEXT)      │
│ modified_by (VARCHAR) │
│ timestamp (TIMESTAMP) │
└───────────────────────┘
```

---

## 2. Table Specifications

### A. `documents` Table
Tracks raw uploaded files, processing status, and raw extracted content.
* `id`: UUID (Primary Key).
* `filename`: Original uploaded filename.
* `file_type`: MIME type / format (`pdf`, `png`, `jpg`, `tiff`, `xlsx`, `csv`).
* `file_size`: File size in bytes.
* `file_path`: Internal storage reference.
* `status`: Processing state (`PENDING`, `PROCESSING`, `VERIFIED`, `NEEDS_REVIEW`, `FAILED`).
* `error_details`: Error message if processing fails.
* `raw_text`: Complete unformatted text extracted from the document.
* `embedding`: Text embedding vector for semantic search.
* `created_at`: Ingestion timestamp.
* `updated_at`: Last modification timestamp.

### B. `invoice_extractions` Table
Stores structured invoice data extracted by AI or manually corrected.
* `id`: UUID (Primary Key).
* `document_id`: Foreign Key referencing `documents.id`.
* `invoice_number`: Unique invoice identifier code.
* `invoice_date`: Document issue date.
* `supplier_name`: Issuing vendor/organization.
* `customer_name`: Recipient organization or client.
* `subtotal`: Net amount before taxes.
* `tax`: Total tax/VAT/GST amount.
* `total`: Gross payable amount.
* `currency`: Currency indicator (e.g. `USD`, `EUR`, `GBP`).
* `confidence_score`: Average extraction confidence ($0.0 - 1.0$).
* `is_manually_corrected`: Boolean flag indicating operator modifications.

### C. `invoice_items` Table
Normalized table storing individual line items for each invoice.
* `id`: UUID (Primary Key).
* `extraction_id`: Foreign Key referencing `invoice_extractions.id`.
* `description`: Line item description/product name.
* `quantity`: Quantity purchased.
* `unit_price`: Unit price per item.
* `amount`: Extended amount ($\text{quantity} \times \text{unit\_price}$).

### D. `validation_errors` Table
Automated business and arithmetic validation findings.
* `id`: UUID (Primary Key).
* `document_id`: Foreign Key referencing `documents.id`.
* `rule_code`: Identifier for rule (e.g., `MATH_SUBTOTAL_MISMATCH`, `DUPLICATE_INVOICE`, `MISSING_FIELD`).
* `severity`: `WARNING`, `ERROR`, or `CRITICAL`.
* `field_name`: Field associated with the issue.
* `error_message`: Human-readable explanation.

### E. `audit_logs` Table
Immutable history of all manual modifications for compliance and review.
* `id`: UUID (Primary Key).
* `document_id`: Foreign Key referencing `documents.id`.
* `changed_field`: The property that was updated.
* `old_value`: Value prior to change.
* `new_value`: Updated value.
* `modified_by`: Identifier of user or operator (`operator_manual`).
* `timestamp`: UTC timestamp of the change.
