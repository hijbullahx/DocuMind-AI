# DocuMind-AI: Enterprise Document Intelligence & Financial Validation System

An AI-powered document intelligence and automated validation platform designed to ingest high-volume, multi-format financial documents, extract structured invoice entities, perform mathematical and cross-document reconciliation, and provide fast keyword, full-text, and semantic search via a modern web interface and REST API.

---

## 🎯 Project Overview & Business Scenario
Organizations handle thousands of business documents daily—including digital invoices, receipts, scanned PDFs, images, Excel spreadsheets, and CSV files. Manual extraction and verification of financial data is time-consuming, prone to human error, and difficult to audit.

**DocuMind-AI** solves this challenge by:
1. **Automating Multi-Format Ingestion**: High-throughput extraction across digital PDFs, scanned documents (OCR), images (PNG, JPG, TIFF), and tabular spreadsheets (XLSX, XLS, CSV).
2. **AI Information Extraction**: Zero-hallucination extraction of header and line-item entities into validated, structured JSON schemas.
3. **Deterministic Financial Validation**: Automated audit rules checking arithmetic integrity ($\sum \text{items} = \text{subtotal}$, $\text{subtotal} + \text{tax} = \text{total}$), duplicate invoices, and cross-document reconciliation (PDF-to-PDF and PDF-to-Excel).
4. **Hybrid Search Engine**: PostgreSQL Full-Text Search (FTS) paired with vector-based semantic search across document contents.
5. **Interactive Operator Dashboard**: Clean web UI for batch uploads, queue monitoring, extraction inspection, validation alert review, and manual corrections.

---

## 🏗️ System Architecture
```
+--------------------------------------------------------------------+
|                         Frontend Web App                           |
|                 React + Vite + Tailwind CSS + Lucide               |
|         - Batch Upload Zone   - Queue Monitor   - Extraction UI    |
+----------------------------------^---------------------------------+
                                   | REST / JSON
+----------------------------------v---------------------------------+
|                         Backend API Layer                          |
|             Django 5.x + Django REST Framework (DRF)               |
|  - Ingestion Endpoints   - Job Orchestrator    - Search API        |
+---------+------------------------+------------------------+--------+
          |                        |                        |
+---------v--------+      +--------v--------+      +--------v--------+
| Ingestion Engine |      | AI & Validation |      | Persistence     |
| - PyMuPDF / FitZ |      | - LLM Extraction|      | - PostgreSQL 15+|
| - pdfplumber     |      |   (Schema Guard)|      | - Full-Text Srch|
| - EasyOCR/Tesseract     | - Math Auditor  |      | - pgvector      |
| - openpyxl/pandas|      | - Cross-Verifier|      | - Audit Trails  |
+------------------+      +-----------------+      +-----------------+
          |                        |
+---------v------------------------v--------+
|      Async Task Queue (Celery + Redis)    |
+-------------------------------------------+
```

---

## 📂 Repository Structure
```text
DocuMind-AI/
├── README.md                      # Project documentation and quickstart
├── docs/                          # Architecture, schema, and requirements specs
│   ├── requirements.md            # Detailed requirement breakdown
│   ├── architecture.md            # Architecture & data flow design
│   ├── database-schema.md         # Database schema & entity models
│   ├── development-plan.md        # 5-day Agile implementation plan
│   ├── progress.md                # Task tracking and milestone log
│   └── ai-disclosure.md           # AI assistance & prompt transparency
├── backend/                       # Django + DRF backend application
│   ├── documind/                  # Django project configuration & Celery setup
│   ├── apps/                      # Modular services: ingestion, extraction, validation, search, api
│   └── tests/                     # Automated test suites
├── frontend/                      # React + Vite + Tailwind CSS dashboard
└── data/                          # Sample files, test datasets, and benchmarks
    ├── samples/                   # Representative input documents
    ├── eval/                      # Labeled evaluation benchmark dataset
    ├── uploads/                   # Runtime storage for uploaded files (gitignored)
    └── processed/                 # Runtime storage for intermediate outputs (gitignored)
```

---

## 🚀 Getting Started (Setup Instructions)

### Prerequisites
- **Python**: 3.11+
- **Node.js**: 18+ (tested with v24)
- **PostgreSQL**: 15+
- **Redis**: For Celery background task processing
- **Git**: Installed and configured

### Quickstart Guide
*(Detailed step-by-step setup and environment configuration will be maintained here as we build each module).*

---

## 🛡️ License & Assessment Compliance
Developed as part of the Senior AI Engineer Assessment project under an incremental Agile methodology. All AI-assisted development tools and prompt engineering methodologies are fully disclosed in [docs/ai-disclosure.md](docs/ai-disclosure.md).
