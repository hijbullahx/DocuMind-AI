# System Architecture & Technical Design
**DocuMind-AI: Enterprise Document Intelligence & Financial Validation System**

---

## 1. High-Level Architecture Overview

DocuMind-AI uses a decoupled, service-oriented architecture designed for reliability, maintainability, and responsiveness when handling heavy document processing workloads.

```text
                       [ Operator / Web Client ]
                                   │
                                   ▼ HTTP / REST
                     ┌───────────────────────────┐
                     │    FastAPI Application    │
                     │  (Routers, Auth, Schema)  │
                     └─────────────┬─────────────┘
                                   │
           ┌───────────────────────┼───────────────────────┐
           ▼                       ▼                       ▼
┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
│ Document Ingestion  │ │ AI Extraction &     │ │ Persistence &       │
│ Engine              │ │ Validation Engine   │ │ Search Engine       │
│                     │ │                     │ │                     │
│ • PyMuPDF / FitZ    │ │ • LLM Client        │ │ • SQLite / Postgres │
│ • pdfplumber        │ │   (Pydantic Schema) │ │ • SQLAlchemy 2.0    │
│ • Tesseract OCR     │ │ • Math Audit Rules  │ │ • Vector Embeddings │
│ • openpyxl / pandas │ │ • Cross-Verifier    │ │ • Audit Trail Log   │
└─────────────────────┘ └─────────────────────┘ └─────────────────────┘
```

---

## 2. Component Breakdown

### A. API & Orchestration Layer (FastAPI)
* **Framework**: FastAPI (Python 3.11+).
* **Rationale**: Python natively supports the best-in-class document processing and AI data science libraries without requiring multi-process bridge hacks. FastAPI offers native async performance, Pydantic v2 data validation, and automated OpenAPI documentation.
* **Background Worker**: File ingestion and OCR are CPU-intensive. Background tasks decouple ingestion requests from the HTTP loop, returning an immediate `202 Accepted` job token so the client can poll or track progress.

### B. Ingestion Pipeline
1. **MIME & Integrity Validation**: Inspects file headers (magic bytes) to ensure safety and prevent malicious payload uploads.
2. **Strategy Router**:
   * **PDF (Digital)**: Extracted using `PyMuPDF` / `pdfplumber` for instant, high-fidelity vector text and table extraction.
   * **PDF (Scanned) & Images (PNG, JPG, TIFF)**: Preprocessed via `Pillow` (contrast enhancement, binarization) and passed to `Tesseract OCR`.
   * **Spreadsheets (XLSX, XLS, CSV)**: Parsed with `openpyxl` and `pandas` into structured row-column representations.

### C. AI Information Extraction & Guardrails
* **Structured Outputs**: Prompts are coupled with strict JSON Schema / Pydantic models. The LLM is constrained to output valid JSON matching the exact schema.
* **Zero-Hallucination Design**: The prompt specifically instructs the model to return `null` for any field that cannot be explicitly identified in the text.
* **Confidence Scoring**: Each extracted field includes an estimated confidence metric based on presence, formatting regularity, and source quality.

### D. Financial Validation Engine
* Runs immediately after AI extraction to enforce business logic:
  * Arithmetic checks: Line item sums vs. Subtotal, Subtotal + Tax vs. Total.
  * Duplicate detection: Hash matching on Supplier Name + Invoice Number.
  * PDF-to-Excel & PDF-to-PDF cross-matching.
* Sets document verification state (`VERIFIED` vs `NEEDS_REVIEW`).

### E. Persistence & Hybrid Search
* **Database**: Relational models (via SQLAlchemy 2.0) storing documents, extracted invoice headers, line items, validation errors, and audit changes.
* **Hybrid Search**:
  * **Keyword Search**: SQL queries over indexed fields (`supplier_name`, `invoice_number`, `date`, `total`).
  * **Semantic Search**: Text embeddings generated from raw document text, enabling natural language similarity queries (e.g., "Find all consulting invoices from last quarter").

---

## 3. Data Flow Diagram
```text
File Upload ──> Validation ──> File Storage ──> Queue Job (202 Accepted)
                                                     │
                                                     ▼
Text / OCR / Table Extraction <──────────────────────┘
         │
         ▼
Prompt Assembly + LLM Structured Extraction
         │
         ▼
Deterministic Financial Validation Rules (Math Audit + Duplicate Check)
         │
         ▼
Persist Record (Status: VERIFIED or NEEDS_REVIEW) + Generate Embeddings
         │
         ▼
Client Polls / Fetches Result ──> Operator Review & Manual Override (Audit Logged)
```
