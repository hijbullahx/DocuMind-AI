# 5-Day Agile Development Plan & Sprint Backlog (Revised)
**DocuMind-AI: Enterprise Document Intelligence System**
**Stack**: React + Vite + Tailwind CSS | Django + DRF | PostgreSQL | Celery + Redis

---

## Sprint Overview & Daily Milestones

| Sprint / Day | Focus Area | Key Deliverables | Status |
| :--- | :--- | :--- | :--- |
| **Day 1: Sprint 0 & 1** | Foundation & Modular Ingestion | Django backend scaffold, React+Vite frontend init, PyMuPDF+pdfplumber PDF parser, OCR engine evaluation (EasyOCR vs Tesseract), Spreadsheet parser, Ingestion tests | In Progress |
| **Day 2: Sprint 2 & 3** | AI Extraction & Validation | Pydantic Schema, LLM structured extraction service, Math auditor, Duplicate detector, PDF-PDF and PDF-Excel cross-reconciliation | Pending |
| **Day 3: Sprint 4** | Async Queue, API & Search | Celery+Redis worker setup, PostgreSQL models & migrations, DRF REST endpoints (upload, status, results, corrections), PostgreSQL FTS | Pending |
| **Day 4: Sprint 5** | Frontend Dashboard | React + Vite + Tailwind UI, Drag-and-drop batch upload, Queue progress board, Side-by-side inspection, Inline correction editor | Pending |
| **Day 5: Sprint 6 & 7** | Search & Benchmark | PostgreSQL FTS + semantic search evaluation, Labeled benchmark evaluation, Accuracy & latency metrics report, Video walkthrough, Final submission audit | Pending |

---

## Detailed Task Breakdown

### Day 1: Foundation & Modular Document Ingestion
* **TASK-001: Project Architecture Finalization & Git Synchronization**
  * Objective: Establish repo structure, revised documentation, `.gitignore`, and push baseline.
  * Status: Complete.
* **TASK-002: Modular Ingestion Core & Digital PDF Extractor**
  * Objective: Create standalone `backend/apps/ingestion/` module with `BaseParser` interface; implement `PDFParser` combining `PyMuPDF` (fast text extraction) and `pdfplumber` (table structure).
  * Acceptance Criteria: Ingests single-page and multi-page PDFs, extracts text with coordinate metadata, handles corrupted files gracefully; verified via unit tests.
* **TASK-003: Modular OCR Engine Evaluation & Implementation**
  * Objective: Implement `OCREngine` supporting EasyOCR and Tesseract fallback; image preprocessing (grayscale, contrast thresholding via Pillow).
  * Acceptance Criteria: Successfully extracts text from test images (PNG, JPG, TIFF) and scanned PDF pages.
* **TASK-004: Spreadsheet & CSV Parser**
  * Objective: Build `SpreadsheetParser` supporting multi-sheet `.xlsx`, `.xls`, and `.csv` using `openpyxl` and `pandas`.
  * Acceptance Criteria: Converts sheets to structured row/table representation and unified text stream.
* **TASK-005: Unified Ingestion Pipeline & Corrupted File Guard**
  * Objective: Build `DocumentIngestionService` routing files by MIME/magic bytes with full error handling.
  * Acceptance Criteria: 100% test coverage over valid, corrupted, empty, and unsupported file formats.

### Day 2: AI Information Extraction & Deterministic Validation
* **TASK-006: Invoice Pydantic Schemas & Anti-Hallucination Prompts**
  * Objective: Define exact schemas for `InvoiceHeader`, `LineItem`, `InvoiceExtractionResult` with explicit `null` enforcement.
* **TASK-007: LLM Extraction Client with Structured Output Mode**
  * Objective: Modular LLM wrapper (Gemini / OpenAI API) enforcing JSON Schema, error handling, retries, and confidence scoring.
* **TASK-008: Deterministic Financial Validation Engine**
  * Objective: Enforce arithmetic consistency: $\sum \text{items} = \text{subtotal}$, $\text{subtotal} + \text{tax} = \text{total}$; identify missing critical fields and duplicate invoices.
* **TASK-009: PDF-PDF & PDF-Excel Cross-Verification Engine**
  * Objective: Implement cross-document reconciliation matching line items, invoice numbers, and totals across paired documents (e.g. PO vs Invoice or Invoice vs Ledger).

### Day 3: Persistence, Celery Queue & Backend API
* **TASK-010: Django Models, PostgreSQL Schema & Migrations**
  * Objective: Configure Django ORM models for `Document`, `InvoiceExtraction`, `LineItem`, `ValidationError`, `AuditLog`.
* **TASK-011: Celery Async Task Worker & Redis Integration**
  * Objective: Configure Celery tasks (`process_document_task`) with `--pool=solo` for Windows compatibility and eager mode for tests.
* **TASK-012: Django REST Framework Endpoints**
  * Objective: Implement endpoints:
    * `POST /api/v1/documents/upload/` (batch upload)
    * `GET /api/v1/documents/` (list with status filters)
    * `GET /api/v1/documents/<id>/` (full extraction, raw text, validation log)
    * `POST /api/v1/documents/<id>/correct/` (manual edit + audit log)
    * `POST /api/v1/documents/<id>/reprocess/` (retry failed jobs)
* **TASK-013: PostgreSQL Full-Text Search (FTS)**
  * Objective: Implement `SearchVector` and `SearchQuery` indexing over document text, supplier, and invoice number; evaluate `pgvector` for semantic queries.

### Day 4: Frontend Operator Dashboard (React + Vite + Tailwind)
* **TASK-014: Frontend Scaffolding & Design System**
  * Objective: Initialize Vite + React + Tailwind CSS project with modular components (Navbar, Sidebar, Metric Cards).
* **TASK-015: Drag-and-Drop Batch File Upload & Queue Monitor**
  * Objective: Batch upload interface with real-time polling on Celery task status (`QUEUED`, `PROCESSING`, `VERIFIED`, `NEEDS_REVIEW`, `FAILED`).
* **TASK-016: Document Review & Side-by-Side Verification Workbench**
  * Objective: Interactive viewer showing raw document text, structured extraction fields, and color-coded validation error badges.
* **TASK-017: Manual Correction Editor & Audit History View**
  * Objective: Form allowing operators to modify fields, trigger recalculation, and view audit trail.
* **TASK-018: Search & Cross-Verification Interface**
  * Objective: Search bar supporting keyword filtering and reconciliation view for comparing two documents side-by-side.

### Day 5: Testing, Empirical Benchmark & Final Submission
* **TASK-019: Automated Test Suite Execution**
  * Objective: Run complete backend (Django tests) and frontend tests; test error handling and edge cases.
* **TASK-020: Empirical Benchmark Evaluation & Report Generation**
  * Objective: Evaluate extraction accuracy, processing speed per page, and success rates on a labeled benchmark dataset; output `docs/evaluation-report.md`.
* **TASK-021: Recorded Walkthrough Script & Final Submission Package**
  * Objective: Verification checklist, final documentation audit, and submission prep.
