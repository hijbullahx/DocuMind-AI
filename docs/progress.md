# Project Progress & Status Tracker
**Project**: DocuMind-AI  
**Last Updated**: 2026-11-04  
**Final Stack**: React + Vite + Tailwind CSS | Django + DRF | PostgreSQL | Celery + Redis | PyMuPDF & pdfplumber | EasyOCR/Tesseract

---

## Current Status: Sprint 1 (Document Ingestion Engine)

| Metric | Current Value |
| :--- | :--- |
| **Active Sprint** | Day 1 - Sprint 1 (Document Ingestion Pipeline) |
| **Current Task** | TASK-003: Modular OCR Engine Evaluation & Implementation (Completed, Awaiting Review) |
| **Completed Tasks** | 3 / 21 |
| **Remaining Days** | 5 Days |
| **Default Test Suite** | 25 passed, 1 skipped in 3.61s (100% offline & mock-based) |
| **Real OCR Smoke Test** | PASSED in 26.53s (Opt-in via RUN_REAL_OCR_SMOKE=1) |
| **Blocking Issues** | None. Awaiting final user review before Git commit and proceeding to TASK-004. |

---

## Architectural & Technical Decisions Log
1. **Repository**: `DocuMind-AI` on GitHub, synchronized and verified.
2. **Backend Framework**: **Django 5.x + Django REST Framework (DRF)**.
   * *Rationale*: Built-in ORM, admin inspection panel, robust database migration framework, out-of-the-box security against common web vulnerabilities.
3. **Frontend Framework**: **React + Vite + Tailwind CSS**.
   * *Rationale*: Fast build/HMR cycle, decoupled SPA architecture, lightweight and clean component-driven UI.
4. **Database & Search**: **PostgreSQL 15+**.
   * *Rationale*: Relational data integrity for invoices, line items, and audit logs. Phase 1 search powered by PostgreSQL native Full-Text Search (FTS). Phase 2 evaluates `pgvector` for semantic search.
5. **Background Tasks**: **Celery + Redis**.
   * *Rationale*: Distributed job management to keep document ingestion and LLM calls non-blocking. Windows compatibility handled via `--pool=solo` and `CELERY_TASK_ALWAYS_EAGER=True` for test isolation.
6. **PDF Processing**: **PyMuPDF (`fitz`) + `pdfplumber`**.
   * *Rationale*: Dual-engine approach provides high-speed vector text parsing combined with precise tabular layout extraction.
7. **OCR Strategy**: **Modular Engine (EasyOCR / Tesseract)**.
   * *Rationale*: EasyOCR requires no external system binary on Windows; modular design allows switching or falling back gracefully.
8. **Modularity**: Ingestion, AI Extraction, Validation, and Search are built as standalone services inside `backend/apps/` so they can be developed and tested independently from the web layer.

---

## Task Log

- [x] **TASK-001**: Project architecture finalization, repository setup, Git remote sync.
- [x] **TASK-002**: Modular Ingestion Core & Digital PDF Extractor.
  - Implemented `backend/apps/ingestion/base.py`: Abstract parser interface, Pydantic data contracts (`ExtractionStatus`, `PageExtraction`, `DocumentMetadata`, `DocumentExtractionResult`).
  - Implemented `backend/apps/ingestion/pdf_parser.py`: PyMuPDF (`pymupdf`) vector text parser + `pdfplumber` structured table extraction.
  - Verified 14 automated unit tests.
- [x] **TASK-003**: Modular OCR Engine Evaluation & Implementation.
  - Evaluated EasyOCR vs. Tesseract for Windows OS; selected EasyOCR with `BaseOCREngine` abstraction to avoid external C++ binary installers.
  - Implemented `backend/apps/ingestion/ocr_engine.py`: `OCRResult`, `BaseOCREngine`, `EasyOCREngine` (with lazy PyTorch model loading and Pillow contrast enhancement), and `MockOCREngine` (for deterministic, network-free unit tests).
  - Implemented `backend/apps/ingestion/image_parser.py`: Standalone parser for PNG, JPG, JPEG, and TIFF files.
  - Integrated PyMuPDF high-resolution page rendering (`page.get_pixmap(dpi=200)`) and selective OCR routing in `PDFParser`. Blank pages and digital pages never trigger OCR.
  - Implemented deterministic post-OCR state recomputation and dedicated `ocr_warnings: List[str]` diagnostics.
  - Verified default test suite: 34 passed, 1 skipped in 4.33s (includes all 14 TASK-002 regression tests and 20 mock unit tests).
  - Verified real EasyOCR opt-in smoke test: PASSED in 26.53s (`RUN_REAL_OCR_SMOKE=1`).
- [x] **TASK-004**: Spreadsheet & CSV Parser (openpyxl & pandas for XLSX, XLS, CSV).
  - Implemented `backend/apps/ingestion/spreadsheet_parser.py`: Standalone `SpreadsheetParser` supporting `.xlsx` (via openpyxl), legacy `.xls` (via xlrd), and `.csv` (via standard csv reader with delimiter sniffing).
  - Multi-sheet workbooks map 1:1 to `PageExtraction` contracts with structured 3D table extraction (`PageExtraction.tables`) and readable Markdown tabular text (`PageExtraction.text`).
  - Implemented deterministic blank sheet detection, empty file handling, corrupted container guards, and in-memory bytes support.
  - Verified 14 automated unit tests in `tests/test_spreadsheet_parser.py`.
  - Full backend test suite passing: 48 passed, 1 skipped in 6.45s (14 PDF tests, 20 OCR tests, 14 spreadsheet tests).
- [x] **TASK-005**: Unified Document Ingestion Pipeline & Corrupted File Guard.
  - Implemented `backend/apps/ingestion/ingestion_service.py`: `DocumentIngestionService` unifying `PDFParser`, `ImageParser`, and `SpreadsheetParser`.
  - Added multi-level format detection: extension matching with magic byte sniffing (`%PDF-`, PNG, JPEG, TIFF, OpenXML `PK\x03\x04`, OLE2, CSV text heuristics).
  - Implemented corrupted file guard: zero-byte empty file detection, non-existent file handling, unhandled parser exception isolation, and unsupported format rejection.
  - Verified 18 automated unit tests in `tests/test_ingestion_service.py`.
  - Full backend test suite passing: 66 passed, 1 skipped in 5.21s (14 PDF, 20 OCR, 14 spreadsheet, 18 ingestion service tests).
- [x] **TASK-006**: Invoice Pydantic Schema & Zero-Hallucination Prompt Design.
  - Implemented `backend/apps/extraction/schemas.py`: Pydantic v2 schemas (`InvoiceExtraction`, `LineItemExtraction`) with strict validation, `Decimal` precision for monetary amounts, and defensive type coercion.
  - Enforced zero-hallucination contract: unknown/missing values normalize strictly to `None` across all fields (including `supplier_address` and `customer_address`), prohibiting hallucinated zeros, fake dates, or arithmetic guesswork.
  - Implemented `_clean_decimal_str`: strictly validates standard US/UK comma grouping (`\d{1,3}(,\d{3})+(\.\d+)?`), strips single currency symbols without identity confusion or currency hallucination, rejects `NaN`/`Infinity`, and rejects malformed/ambiguous formats (`1,2`, `1,2,3`, `1,,000`, `$100 €`).
  - Documented negative values & European format: negative amounts / credit notes are intentionally unsupported by this payable schema and rejected (`ge=0`); European decimal-comma formats (`1250,50`, `1.250,50`) are explicitly rejected as ambiguous rather than silently interpreted to prevent 100x calculation errors.
  - Documented `raw_text_evidence`: models extraction claims provided by the LLM; does not independently verify substring presence against original source text (cross-document verification is evaluated in TASK-008/TASK-009).
  - Implemented `backend/apps/extraction/prompts.py`: Zero-hallucination system prompt (`INVOICE_EXTRACTION_SYSTEM_PROMPT`) prohibiting arithmetic fabrication and speculative extrapolation; prompt builder with `<DOCUMENT_CONTENT>` boundary tag isolation and escaping of embedded tags (`&lt;/DOCUMENT_CONTENT&gt;`) against tag-smuggling injection. Unit tests verify template structure and escaping; actual model resistance requires LLM execution in TASK-007.
  - Implemented defensive JSON parsing helper `InvoiceExtraction.from_raw_json()` handling clean JSON, markdown code fence stripping (````json ... ````), and raising `ExtractionSchemaError`.
  - Added 26 automated unit and security tests in `backend/tests/test_extraction_schema.py`.
  - Full backend test suite passing: 92 passed, 1 skipped in 5.82s (14 PDF, 20 OCR, 14 spreadsheet, 18 ingestion service, 26 extraction schema tests).
- [x] **TASK-007**: LLM Extraction Client with Structured Outputs.
  - Implemented `backend/apps/extraction/llm_client.py`: Modular LLM extraction client (`LLMExtractionClient`) with provider abstraction (`BaseLLMProvider`).
  - Supported providers: `MockLLMProvider` (deterministic offline testing and CI), `GeminiProvider` (Google Gemini REST API with schema inlining and key redaction), and `OpenAIProvider` (OpenAI REST API with strict Structured Outputs mode `response_format: {"type": "json_schema", "json_schema": {"strict": True, "schema": ...}}`).
  - Implemented provider-specific schema adaptation:
    * `_adapt_schema_for_openai_strict`: Recursively enforces `additionalProperties: false`, requires all properties (with nullable `anyOf: [..., {"type": "null"}]`), adapts dynamic `raw_text_evidence` to explicit optional properties, and recursively strips unsupported Pydantic keywords (`default`, `title`) to satisfy strict JSON Schema validation without mutating the shared TASK-006 schema.
    * `_inline_json_schema`: Deep-copies and inlines `$defs` / `$ref` for Google Gemini `responseSchema` compatibility.
  - Implemented exponential backoff retries on transient network/timeout errors, immediate failure for non-retriable HTTP errors (400, 401, 403), and sanitized error reporting preventing API key leakage.
  - Implemented heuristic evidence-grounding scoring (`compute_evidence_confidence`): evaluates verbatim and non-stopword token overlap of `raw_text_evidence` quotes against source text; null fields receive `None` (`NOT_APPLICABLE`) and do not inflate composite grounding scores.
  - Added 30 automated unit and mocked HTTP contract tests in `backend/tests/test_llm_client.py` covering clean extraction, markdown fences, exact/partial/unmatched grounding semantics, null field exclusion, stopword filtering, Gemini payload schema inlining, OpenAI strict mode `response_format` structure, unstructured fallback, key redaction, timeout retries, non-retriable HTTP codes, and prompt boundary sealing.
  - Full backend test suite passing: 122 passed, 1 skipped in 4.64s (14 PDF, 20 OCR, 14 spreadsheet, 18 ingestion service, 26 extraction schema, 30 LLM client tests).
  - Testing Level & Limitations:
    * Unit Tests: Verified client coordination, prompt construction, parsing, and failure recovery.
    * Mocked HTTP Contract Tests: Verified Gemini and OpenAI payload formatting, strict schema adaptation, and header redaction without external network calls.
    * Live Provider Tests: Unverified because live paid API credentials are not configured in this environment; real neural injection resistance requires live inference.
- [x] **TASK-008**: Deterministic Financial Validation Engine.
  - Implemented `backend/apps/validation/`: Standalone deterministic financial validation package.
  - Implemented `models.py`: `ValidationStatus` (`VERIFIED`, `NEEDS_REVIEW`, `FAILED`), `ValidationSeverity` (`ERROR`, `WARNING`, `INFO`), `ValidationRuleId`, `ValidationError`, and `ValidationResult`.
  - Implemented `math_rules.py`:
    * Line Item Sum Check: $|\sum(\text{line\_item.amount}) - \text{subtotal}| \le 0.05$ with automatic calculation from $quantity \times unit\_price$ when item amount is omitted.
    * Tax Addition Check: $|\text{subtotal} + \text{tax} - \text{total}| \le 0.05$, validating zero tax when subtotal equals total and rejecting tax exceeding total.
    * Itemized Calculation Check: $|\text{quantity} \times \text{unit\_price} - \text{amount}| \le 0.05$ across all line items.
  - Implemented `anomaly_rules.py`:
    * Missing critical field guard: triggers `ERROR` for missing `invoice_number`, `invoice_date`, or `total`; `WARNING` for missing `supplier_name`.
    * Duplicate invoice detector: normalized, case- and whitespace-insensitive matching on `(supplier_name, invoice_number)` with `InMemoryDuplicateDetector` and pluggable protocol.
    * Date validity & chronological guard: calendar parsing via `dateutil`, past threshold warning (year < 2000), future threshold warning (> 365 days), and chronological contradiction check (`due_date < invoice_date` triggers `ERROR`).
    * Negative amount guard: rejects negative values across totals and line items.
  - Implemented `engine.py`: `ValidationEngine` coordinating schema coercion (from model, dict, or JSON string), anomaly checks, mathematical rules, and status determination (`VERIFIED`, `NEEDS_REVIEW`, `FAILED`).
  - Added 53 automated unit and audit regression tests in `backend/tests/test_validation_engine.py` covering exact tolerance boundaries (0.05 vs 0.051), float tolerance safety, indeterminate item amounts, null tax review rules, duplicate detection collision prevention, date boundary plausibility, status precedence, and serialization.
  - Full backend test suite passing: 175 passed, 1 skipped in 5.21s (14 PDF, 20 OCR, 14 spreadsheet, 18 ingestion service, 26 extraction schema, 30 LLM client, 53 validation engine tests).
- [x] **TASK-009**: PDF-PDF & PDF-Excel Cross-Verification Engine.
  - Implemented `backend/apps/validation/cross_verifier.py`: `CrossDocumentVerifier`, `CrossVerificationResult`, `CrossDocumentDiscrepancy`, `CrossVerificationRuleId`.
  - Reconciles paired documents across:
    * Total, subtotal, and tax amounts with configurable arithmetic tolerance (default $\le 0.05$).
    * Currency normalization and conflict detection (symbol mapping `$` $\to$ `USD`, `€` $\to$ `EUR`, `£` $\to$ `GBP`).
    * Supplier legal entity name and customer recipient name matching with entity punctuation normalization.
    * Reference / invoice number matching supporting both flexible PO-Invoice mode (`WARNING`) and strict invoice mode (`ERROR`).
    * Line items cross-reconciliation using global bipartite candidate ranking `(-sim, -amount_match, idx_a, idx_b)`: prioritizes exact description matches and matching amounts before partial overlap ($\ge 0.70$) regardless of input document list order. Compares item quantity, unit price, and line amount, with unmatched item detection (`CROSS_UNMATCHED_ITEM`).
    * Conservative missing/null handling: missing totals or figures are not treated as false mismatches but flag actionable `CROSS_INCOMPLETE_COMPARISON` review warnings.
    * Multi-format support: reconciles PDF-PDF pairs, PDF-Excel/CSV spreadsheet rows, raw JSON strings, and `DocumentExtractionResult` tables.
    * Duplicate discrepancy suppression and deterministic output ordering with indexed line item field paths (`line_items[{idx}].quantity`, `line_items[{idx}]`) preventing suppression collisions across distinct items sharing identical descriptions.
  - Added 32 automated unit tests in `backend/tests/test_cross_verifier.py` covering matching pairs, financial discrepancies, quantity/price overcharges, conservative missing data handling, reference matching modes, spreadsheet/tabular reconciliation, line item ranking and order independence, multiple identical items, exact tolerance boundaries (0.05 vs 0.051), and JSON serialization.
  - Full backend test suite passing: 207 passed, 1 skipped in 5.16s (14 PDF, 20 OCR, 14 spreadsheet, 18 ingestion service, 26 extraction schema, 30 LLM client, 53 validation engine, 32 cross-verifier tests).
- [x] **TASK-010**: Django Models, PostgreSQL Schema & Migrations.
  - Configured Django project structure: `backend/manage.py`, `backend/documind/` (`settings.py`, `urls.py`, `wsgi.py`).
  - Implemented `backend/apps/documents/models.py`:
    * `Document`: Root container with UUID primary key, file upload field, metadata JSONField, pipeline status (`QUEUED`, `PROCESSING`, `SUCCESS`, `PARTIAL_SUCCESS`, `FAILED`), and validation status (`PENDING`, `VERIFIED`, `NEEDS_REVIEW`, `FAILED`).
    * `InvoiceExtraction`: 1:1 structured financial extraction with strict Decimal fields (`subtotal`, `tax`, `total`), nullable fields for zero-hallucination compliance, and `raw_text_evidence` JSON mapping.
    * `LineItem`: ForeignKey to `InvoiceExtraction` with line numbers, descriptions, 4-decimal quantity/unit price, and line amounts.
    * `ValidationError`: ForeignKey to `Document` recording rule IDs, affected fields, severity (`ERROR`, `WARNING`, `INFO`), actual/expected values, arithmetic differences, and operator dismissal fields (`is_dismissed`, `dismissed_by`, `dismissed_at`).
    * `AuditLog`: Immutable audit trail tracking operator manual corrections, overrides, status changes, reasons, and timestamps, with model-level update and direct deletion protection.
    * `CrossReconciliation`: Relational record of paired document verification (`doc_a`, `doc_b`) with status, discrepancies/warnings JSONField, item match counts, summary, and `prevent_self_reconciliation` database CheckConstraint.
  - Generated and verified reproducible initial migration `apps/documents/migrations/0001_initial.py`.
  - Added 29 automated unit tests in `backend/tests/test_document_models.py` covering model creation, UUID keys, Decimal financial precision, status choices and transition save enforcement, metadata JSON storage, cascade deletions, review dismissals, immutable audit logs, 1:1 extraction uniqueness, self-reconciliation prevention, Pydantic integration compatibility, and migration reproducibility.
  - Full backend test suite passing: 236 passed, 1 skipped in 13.81s (14 PDF, 20 OCR, 14 spreadsheet, 18 ingestion service, 26 extraction schema, 30 LLM client, 53 validation engine, 32 cross-verifier, 29 document models tests).
- [x] **TASK-011**: Celery Async Task Worker & Redis Integration.
  - Configured Celery application `documind.celery.app` and exposed `celery_app` in `backend/documind/__init__.py`.
  - Configured environment-driven Redis broker and backend in `backend/documind/settings.py` (`CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`), with strict JSON serializers, task limits (300s hard / 240s soft), and Windows concurrency guard documentation (`--pool=solo` / `--pool=threads`).
  - Added `celery>=5.3.0` and `redis>=5.0.0` to `backend/requirements.txt`.
  - Implemented asynchronous Celery tasks in `backend/apps/documents/tasks.py`:
    * `process_document_task(document_id, force=False, provider=None, canned_response=None)`: End-to-end background orchestration connecting Document Ingestion (`DocumentIngestionService`), AI Financial Extraction (`LLMExtractionClient`), Deterministic Validation (`ValidationEngine`), and atomic database persistence (`InvoiceExtraction`, `LineItem`, `ValidationError`).
    * `reconcile_documents_task(doc_a_id, doc_b_id, tolerance=None)`: Asynchronous paired document cross-verification (`CrossDocumentVerifier`), recording discrepancies, match counts, and persisting `CrossReconciliation` records.
    * Added atomic conditional database update claims: eliminates multi-worker race conditions on `QUEUED` documents using database-level `UPDATE ... WHERE status = 'QUEUED'`, ensuring only the winning worker claims the document while competing workers return safe non-processing rejections.
    * Added concurrency-safe forced reprocessing (`force=True`): rejects claims if another worker is actively in `PROCESSING` status, preventing duplicate concurrent processing runs while preserving immutable `AuditLog` creation.
    * Added comprehensive error isolation: handles corrupted documents, invalid UUID formats, and missing files with graceful `FAILED` status transitions without unhandled worker crashes.
  - Added 25 automated unit tests in `backend/tests/test_celery_tasks.py` with `CELERY_TASK_ALWAYS_EAGER=True` covering atomic claims, competing worker rejection, repeated task submission idempotency, active processing rejection, forced reprocessing safety, failure handling, and cross-document reconciliation.
  - Focused test suite passing: 139 passed in 29.72s (25 Celery, 29 document models, 53 validation engine, 32 cross-verifier).
  - Full backend test suite passing: 261 passed, 1 skipped (25 Celery, 32 cross-verifier, 29 document models, 26 extraction schema, 18 ingestion service, 30 LLM client, 20 OCR, 14 PDF, 14 spreadsheet, 53 validation engine).
  - Full backend test suite passing: 256 passed, 1 skipped in 22.11s (14 PDF, 20 OCR, 14 spreadsheet, 18 ingestion service, 26 extraction schema, 30 LLM client, 53 validation engine, 32 cross-verifier, 29 document models, 20 Celery task tests).
- [x] **TASK-012**: Django REST Framework Endpoints.
  - Integrated `djangorestframework>=3.14.0` in `backend/requirements.txt` and registered `'rest_framework'` in `backend/documind/settings.py`.
  - Configured REST framework defaults: PageNumberPagination (page size 20), JSON renderer, AllowAny permission baseline for development, max upload size 25 MB, and allowed document extensions (`pdf`, `png`, `jpg`, `jpeg`, `tiff`, `tif`, `xlsx`, `xls`, `csv`, `txt`).
  - Implemented comprehensive serializers in `backend/apps/documents/serializers.py`:
    * `LineItemSerializer`: Serializes extracted line items.
    * `ValidationErrorSerializer`: Serializes deterministic financial validation findings and dismissal status.
    * `AuditLogSerializer`: Serializes immutable audit history entries.
    * `InvoiceExtractionSerializer`: Serializes structured financial extraction results with nested line items.
    * `DocumentListSerializer`: Lightweight document summary serializer.
    * `DocumentDetailSerializer`: Full detail serializer with nested extraction, line items, validation errors, and audit logs.
    * `DocumentStatusSerializer`: Lightweight polling serializer for tracking ingestion/validation state.
    * `DocumentUploadSerializer`: Server-side file validation (size $\le 25\text{MB}$, allowed extensions, non-empty content).
    * `DocumentReprocessSerializer`: Validates retry and force reprocessing requests.
    * `CrossReconciliationRequestSerializer` & `CrossReconciliationSerializer`: Paired document verification request validation and result serialization.
  - Implemented REST viewsets in `backend/apps/documents/views.py`:
    * `DocumentViewSet`:
      - `POST /api/documents/`: Upload document or raw text, enqueue `process_document_task.delay(doc_id)`.
      - `GET /api/documents/`: Paginated list, filterable by `status`, `validation_status`, `file_type`, search by `filename`/`invoice_number`/`supplier_name`, and ordered by `created_at`.
      - `GET /api/documents/{id}/`: Comprehensive detail view with nested extraction, line items, validation errors, and audit history.
      - `GET /api/documents/{id}/status/`: Lightweight polling endpoint.
      - `POST /api/documents/{id}/reprocess/`: Reprocessing/retry endpoint with active-processing conflict guard (409) and force authorization requirement.
    * `CrossReconciliationViewSet`:
      - `POST /api/reconciliations/`: Trigger paired document cross-verification using `reconcile_documents_task`.
      - `GET /api/reconciliations/` & `GET /api/reconciliations/{id}/`: List and retrieve cross-reconciliation findings and discrepancy reports.
  - Routed API endpoints via `apps.documents.urls` registered at `path('api/', include('apps.documents.urls'))` in `backend/documind/urls.py`.
  - Added 23 automated unit tests in `backend/tests/test_document_api.py` covering uploads, constraints, pagination, filtering, search, detail inspection, status polling, reprocessing, and cross-reconciliation.
  - Focused test suite passing: 162 passed in 18.42s (23 document API, 25 Celery, 29 document models, 53 validation engine, 32 cross-verifier).
  - Full backend test suite passing: 284 passed, 1 skipped.
- [x] **TASK-013**: PostgreSQL Full-Text Search (FTS).
  - Implemented dedicated search service in `backend/apps/documents/search.py`:
    * Native PostgreSQL Full-Text Search engine using `SearchVector`, `SearchQuery`, and `SearchRank`.
    * 4-tier weighted ranking architecture:
      - Weight A (Highest): `Document.filename`, `InvoiceExtraction.invoice_number`
      - Weight B (Primary Entities): `InvoiceExtraction.supplier_name`, `InvoiceExtraction.customer_name`
      - Weight C (Secondary Details): `InvoiceExtraction.supplier_address`, `InvoiceExtraction.customer_address`, `LineItem.description`
      - Weight D (Document Body): `Document.raw_text` (all OCR text, PDF vector text, and spreadsheet tabular data)
    * Multi-word and phrase parsing using websearch syntax with graceful fallback to plain search.
    * Relevance rank annotation (`search_rank`) and ranking-based ordering (`-search_rank`, `-created_at`).
    * Robust SQLite / development multi-field search fallback ensuring 100% test suite compatibility and offline dev functionality without database errors.
    * Input query sanitization: whitespace normalization, multi-word tokenization, special character and punctuation escaping. Empty or whitespace-only queries bypass search overhead entirely.
  - Added migration `backend/apps/documents/migrations/0002_postgres_fts_indexes.py`:
    * Conditionally creates functional PostgreSQL GIN indexes on `to_tsvector('english', COALESCE(raw_text, ''))` and `to_tsvector('english', COALESCE(filename, ''))` when running on PostgreSQL (`connection.vendor == 'postgresql'`).
    * Gracefully skips execution on SQLite without syntax errors.
  - Integrated search engine into `DocumentViewSet` in `backend/apps/documents/views.py`, preserving existing API response contracts, filtering, pagination, and custom orderings.
  - Added 19 automated tests in `backend/tests/test_search.py` covering all 4 weighted tiers, multi-word tokens across fields, punctuation, quotes, symbols, empty queries, no-result queries, multi-line item deduplication, filter composition, pagination, explicit ordering overrides, and PostgreSQL query builder validation.
  - Full backend test suite passing: 303 passed, 1 skipped in 37.92s across all 12 test modules.
- [ ] **TASK-014**: Frontend Project Scaffolding & Layout.
- [ ] **TASK-015**: Drag-and-Drop Batch Upload & Queue Monitor.
- [ ] **TASK-016**: Document Inspection & Side-by-Side Review Workbench.
- [ ] **TASK-017**: Inline Correction Editor & Audit History.
- [ ] **TASK-018**: Search & Cross-Verification Interface.
- [ ] **TASK-019**: End-to-End Automated Test Suite.
- [ ] **TASK-020**: Empirical Benchmark Evaluation & Report Generation.
- [ ] **TASK-021**: Recorded Walkthrough Script & Final Submission Package.

---

## Technical Audit & Memory/Performance Truth
1. **Memory & Lazy Initialization**:
   * `EasyOCREngine` uses lazy property initialization. If a document is pure digital text, `EasyOCR` is never imported or loaded into RAM.
   * Unit tests inject `MockOCREngine`, ensuring default test runs consume zero model RAM and run in < 4 seconds.
2. **Selective Page Routing**:
   * Blank pages (`is_blank=True`) are strictly bypassed and never sent to OCR.
   * Scanned pages (`needs_ocr=True`) are rendered to PIL images and processed individually.
   * If OCR fails on one page, digital text on other pages is preserved, and the document is classified as `PARTIAL_SUCCESS`.
3. **Table & OCR Diagnostic Separation**:
   * `table_extraction_warning` remains strictly for `pdfplumber` issues.
   * `ocr_warnings` records page-specific OCR anomalies or engine exceptions without silently converting errors to empty outputs.
4. **Current Ingestion Limitations**:
   * OCR is configured for printed English/Latin typography; cursive handwriting is out of scope.
   * 1,000-page bulk OCR throughput will be evaluated during the Day 5 benchmark (TASK-020).
