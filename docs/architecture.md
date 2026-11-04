# System Architecture & Technical Design (Revised)
**DocuMind-AI: Enterprise Document Intelligence & Financial Validation System**

---

## 1. High-Level Architecture Overview

DocuMind-AI uses a decoupled, service-oriented architecture designed for reliability, maintainability, and responsiveness when handling heavy document processing workloads.

```text
                       [ Operator / Web Client ]
                       React + Vite + Tailwind CSS
                                   │
                                   ▼ HTTP / JSON (REST)
                     ┌───────────────────────────┐
                     │ Django REST Framework API │
                     │   (Auth, Views, Serializers)│
                     └─────────────┬─────────────┘
                                   │
             ┌─────────────────────┼─────────────────────┐
             ▼                     ▼                     ▼
┌─────────────────────────┐ ┌───────────────┐ ┌──────────────────────┐
│  Celery Task Worker     │ │ Redis Broker  │ │ PostgreSQL 15+       │
│  (Async Ingestion & AI) │ │ (Job Queue)   │ │ • Relational Tables  │
│                         │ └───────▲───────┘ │ • Full-Text Search   │
│ • PyMuPDF & pdfplumber  │         │         │ • Audit History Logs │
│ • EasyOCR / Tesseract   │ ────────┘         │ • pgvector (Semantic)│
│ • openpyxl & pandas     │                   └──────────────────────┘
│ • LLM Structured Output │
│ • Math & Cross-Verifier │
└─────────────────────────┘
```

---

## 2. Technology Stack Selection & Rationale

| Layer | Chosen Technology | Selection Rationale |
| :--- | :--- | :--- |
| **Frontend** | **React + Vite + Tailwind CSS** | Blazing-fast Hot Module Replacement (HMR), minimal boilerplate, lightweight SPA architecture. Decoupled from backend, avoiding SSR overhead while providing responsive UI with Tailwind utility classes. |
| **Backend** | **Django 5.x + Django REST Framework (DRF)** | Enterprise-grade ORM, robust database migrations, built-in admin panel for inspecting raw data, high security out of the box (CSRF, SQL injection protection), and clean serialization/viewset abstraction. |
| **Database** | **PostgreSQL (15+)** | ACID-compliant relational store with native support for `JSONField` (for dynamic extraction payload caching), native **PostgreSQL Full-Text Search** (`SearchVector`, `SearchQuery`, `tsvector`), and optional `pgvector` extension for semantic search. |
| **Queue & Cache** | **Celery + Redis** | Industry-standard async distributed task queue. Separates heavy CPU/network operations (OCR, PDF page parsing, LLM calls) from synchronous API request-response loops. |
| **PDF Extraction**| **PyMuPDF (`fitz`) & `pdfplumber`** | Dual-engine strategy: `PyMuPDF` provides high-speed vector text and layout parsing; `pdfplumber` provides superior table cell coordinate extraction. |
| **OCR Strategy** | **Modular (EasyOCR / Tesseract)** | Modular interface (`BaseOCREngine`). Evaluates EasyOCR (pure Python, bundled deep-learning models, zero system binary prerequisites) vs. Tesseract OCR (fast C++ binary). Graceful fallback ensures pipeline never crashes if one engine is absent. |
| **Spreadsheets** | **openpyxl & pandas** | Native handling of multi-sheet `.xlsx`, legacy `.xls`, and comma-separated `.csv` files. |
| **AI Extraction** | **LLM API (Structured JSON Mode)**| Prompt engineering combined with JSON Schema / Pydantic validation to guarantee zero-hallucination structured invoice outputs. |
| **Search Engine** | **PostgreSQL FTS (initially) → pgvector (semantic)** | Phase 1 leverages PostgreSQL native full-text search with stemming and ranking. Phase 2 introduces vector similarity embeddings for natural language semantic document queries. |

---

## 3. Modular Application Architecture

The backend will follow a modular service design inside Django (`backend/apps/`):

```text
backend/
├── manage.py
├── documind/                     # Project configuration & settings
│   ├── settings.py
│   ├── urls.py
│   ├── celery.py                 # Celery app initialization
│   └── wsgi.py
└── apps/
    ├── documents/                # Models: Document, Extraction, LineItem, ValidationError, AuditLog
    ├── ingestion/                # Modular parsers (independent from web layer)
    │   ├── base.py               # Ingestion interface
    │   ├── pdf_parser.py         # PyMuPDF + pdfplumber
    │   ├── ocr_engine.py         # EasyOCR / Tesseract modular engine
    │   └── spreadsheet_parser.py # openpyxl / pandas
    ├── extraction/               # AI Extraction service
    │   ├── schemas.py            # Pydantic schemas for Invoice & LineItems
    │   ├── prompts.py            # Anti-hallucination prompt definitions
    │   └── llm_client.py         # LLM provider wrapper (Gemini / OpenAI)
    ├── validation/               # Deterministic business rules
    │   ├── math_rules.py         # Sum, Tax, Item total verification
    │   ├── anomaly_rules.py      # Missing fields, duplicate detection
    │   └── cross_verifier.py     # PDF-PDF & PDF-Excel cross reconciliation
    ├── search/                   # Search service
    │   ├── fts.py                # PostgreSQL Full-Text Search indexer & query
    │   └── semantic.py           # Vector embeddings & similarity search
    └── api/                      # DRF Serializers, ViewSets, and URL routers
```

---

## 4. Key Architectural Risks & Mitigation Strategies

1. **Celery Worker on Windows**:
   * *Risk*: The default Celery `prefork` pool encounters multiprocessing bugs on Windows OS.
   * *Mitigation*: Configure Celery to use `--pool=solo` or `--pool=threads` during local Windows execution. For automated tests, configure `CELERY_TASK_ALWAYS_EAGER = True` so tasks run synchronously within tests without requiring an active Redis broker.
2. **Database Availability in Local Environment**:
   * *Risk*: PostgreSQL service might not be running or configured initially on every developer machine.
   * *Mitigation*: Use `django-environ` to allow dynamic switching to SQLite during initial offline development and automated unit testing, while targeting PostgreSQL for full-text search and production.
3. **OCR Engine Dependencies**:
   * *Risk*: Tesseract binary missing from PATH breaks scanned document processing.
   * *Mitigation*: EasyOCR as primary Python-native fallback, or modular strategy pattern where missing OCR binary produces an informative `WARNING` and flags the document rather than unhandled exception.
