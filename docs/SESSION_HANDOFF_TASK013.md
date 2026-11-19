# DocuMind-AI Session Handoff — TASK-013 PostgreSQL FTS Remediation

**Date & Time:** 2026-11-19 15:20 (UTC+6)  
**Branch:** `main`  
**Baseline Commit:** `6cee5337fdd158e154ba60ee6658eaee68ce3155` (`feat: add document REST API`)  
**Checkpoint Commit:** Will be recorded upon commit creation (`wip: checkpoint TASK-013 postgres fts remediation`)  
**Remote Push Status:** Pushed to `https://github.com/hijbullahx/DocuMind-AI.git` on branch `main`

---

## 1. Context & Objective

We are in the middle of **TASK-013 Remediation: PostgreSQL FTS Architecture Fix**. Work was paused to allow shutting down the development machine and resuming tonight on another PC.

### Confirmed Remediation Findings
1. Current PostgreSQL filtering in `backend/apps/documents/search.py` used `ts_rank(compound_vector, query) > 0.0`, which prevents PostgreSQL from performing a Bitmap Index Scan on a GIN index.
2. The initial migration `0002_postgres_fts_indexes.py` added functional GIN indexes on `to_tsvector(raw_text)` and `to_tsvector(filename)`, but the actual search query evaluated an 8-field compound vector across 3 joined tables (`Document`, `InvoiceExtraction`, `LineItem`), bypassing the index.
3. Joining `LineItem` rows dynamically in the search query created a risk of duplicate document rows in search results.
4. Python PostgreSQL driver was missing from `requirements.txt`.

---

## 2. Completed Work So Far

1. **Search Engine Core (`backend/apps/documents/search.py`):**
   - Implemented query sanitization (`sanitize_search_query`), multi-word whitespace normalization, and tokenization (`tokenize_query`).
   - Implemented 4-tier weighted ranking architecture:
     * Weight A: `Document.filename`, `InvoiceExtraction.invoice_number`
     * Weight B: `InvoiceExtraction.supplier_name`, `InvoiceExtraction.customer_name`
     * Weight C: `InvoiceExtraction.supplier_address`, `InvoiceExtraction.customer_address`, `LineItem.description`
     * Weight D: `Document.raw_text`
   - Built SQLite fallback search (`apply_sqlite_fallback_search`) using `icontains` with multi-token AND matching, preserving 100% test suite compatibility.
   - Updated `apply_document_search` to route dynamically based on `connection.vendor`.

2. **REST API Integration (`backend/apps/documents/views.py`):**
   - Connected `apply_document_search` to `DocumentViewSet.get_queryset()`.
   - Preserves filtering (status, validation_status, file_type), custom ordering, and pagination.

3. **Driver Manifest & Installation:**
   - Added `psycopg[binary]>=3.1.0` to `backend/requirements.txt` under `# PostgreSQL Database Driver`.
   - Successfully installed `psycopg` and `psycopg-binary` version `3.3.9` into `backend/venv`.
   - Verified that `psycopg` imports cleanly and `django.contrib.postgres.search.SearchRank` initializes without missing dependency errors.

4. **Repository Hygiene (`.gitignore`):**
   - Added SQLite temporary locks (`*.sqlite3-journal`, `*.sqlite3-wal`, `*.sqlite3-shm`) to `.gitignore` to prevent transient SQLite files from cluttering Git.

5. **Test Suite (`backend/tests/test_search.py`):**
   - 19 automated tests covering sanitization, tokenization, tiers A-D, multi-word matching, quotes, special characters, empty queries, pagination, and filter composition.
   - Verified: 42 tests passed in 10.66s across `test_search.py` and `test_document_api.py`.

---

## 3. Verified Environment Status

- **psycopg status:** Installed in `backend/venv` (`3.3.9`). Verified via `import psycopg; print(psycopg.__version__)`.
- **PostgreSQL service status:** Local port `5432` is listening (`localhost:5432`, `TcpTestSucceeded: True`).
- **Active test database:** SQLite (using fast temp SSD DB `$env:TEMP\test_db.sqlite3` for local tests to avoid virtual drive latency).
- **Django system check:** `python manage.py check` reports 0 issues.
- **Migration check:** `python manage.py makemigrations --check` reports no unhandled schema drift.
- **Git check:** `git diff --check` passes with zero errors.

---

## 4. Work in Progress / Investigation at Pause Time

Before pausing, we verified:
1. `SearchVector(Value(...))` compiles to native PostgreSQL:
   ```sql
   (setweight(to_tsvector('english', COALESCE(%s, '')), 'A') || setweight(to_tsvector('english', COALESCE(%s, '')), 'B') || ...)
   ```
2. `GinIndex` compiles safely without errors on SQLite schema editor.
3. We were designing the persisted `SearchVectorField` on `Document` and its synchronization signals.

---

## 5. Incomplete Work for TASK-013 Remediation

To finalize TASK-013 tonight:

1. **Add `search_vector` field to `Document` model (`backend/apps/documents/models.py`):**
   ```python
   from django.contrib.postgres.search import SearchVectorField
   from django.contrib.postgres.indexes import GinIndex

   # On Document:
   search_vector = SearchVectorField(null=True, blank=True, editable=False)

   # In Document.Meta.indexes:
   GinIndex(fields=['search_vector'], name='doc_search_vector_gin')
   ```

2. **Create / Replace Migration `0002_add_document_search_vector.py`:**
   - Add field `search_vector` to `Document`.
   - Add GIN index `doc_search_vector_gin`.
   - In a `RunPython` step: for existing documents, populate `search_vector` if running on PostgreSQL.

3. **Implement Vector Synchronization (`backend/apps/documents/search.py` & signals):**
   - Helper `update_document_search_vector(document_id)`:
     * Reads `Document`, its `extraction`, and associated `line_items`.
     * If PostgreSQL: executes `Document.objects.filter(id=doc_id).update(search_vector=vector)`.
   - Wire Django `post_save` and `post_delete` signals:
     * On `Document` save (if `filename` or `raw_text` modified).
     * On `InvoiceExtraction` save / delete (updates parent document).
     * On `LineItem` save / delete (updates parent document via `extraction.document`).
   - Also invoke `update_document_search_vector` at the completion of Celery `process_document_task`.

4. **Update `apply_postgres_fts` in `backend/apps/documents/search.py`:**
   - Query directly using the indexable `@@` matching condition:
     ```python
     ranked_qs = (
         queryset
         .filter(search_vector=query_obj)
         .annotate(search_rank=SearchRank(F("search_vector"), query_obj))
         .order_by("-search_rank", "-created_at")
     )
     ```
   - Because `search_vector` is stored on `Document`, this queries `documents_document` directly with NO joins to `LineItem`. This inherently eliminates duplicate document rows and leverages the GIN index via Bitmap Index Scan.

5. **Test Coverage:**
   - Add tests verifying signal updates when `InvoiceExtraction` or `LineItem` descriptions change.
   - Verify SQL compilation for `search_vector=@@` and `SearchRank(F('search_vector'), ...)`.
   - Run the complete 300+ test regression suite.

---

## 6. Exact Instructions for Resuming Tonight on the Other PC

1. **Clone / Pull repository:**
   ```bash
   git pull origin main
   ```
2. **Activate virtual environment & ensure dependencies:**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```
3. **Verify current status:**
   ```bash
   python manage.py check
   pytest tests/test_search.py tests/test_document_api.py
   ```
4. **Continue implementation of the 5 points listed in Section 5 above.**
5. **Run full test suite & audit verification:**
   ```bash
   pytest tests/
   ```
6. **Submit final report and request commit authorization.**
