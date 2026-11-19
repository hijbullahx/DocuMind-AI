"""
Migration adding persisted search_vector field and GIN index to Document model.
Populates search_vector across 4-tier weighting hierarchy:
- Tier A: filename, invoice_number
- Tier B: supplier_name, customer_name
- Tier C: supplier_address, customer_address, line-item descriptions
- Tier D: raw_text

Runs safely on PostgreSQL and non-PostgreSQL (SQLite) backends.
"""
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import migrations


def populate_search_vectors(apps, schema_editor):
    """
    Backfills search_vector for existing documents on PostgreSQL.
    Safely no-ops on SQLite / other database engines.
    """
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as cursor:
            # Clean up obsolete functional GIN indexes from 0002 if present
            cursor.execute("DROP INDEX IF EXISTS doc_raw_text_search_gin;")
            cursor.execute("DROP INDEX IF EXISTS doc_filename_search_gin;")

            # 1. Backfill documents with associated extraction and aggregated line items
            cursor.execute("""
                UPDATE documents_document d
                SET search_vector = (
                    setweight(to_tsvector('english', COALESCE(d.filename, '') || ' ' || COALESCE(e.invoice_number, '')), 'A') ||
                    setweight(to_tsvector('english', COALESCE(e.supplier_name, '') || ' ' || COALESCE(e.customer_name, '')), 'B') ||
                    setweight(to_tsvector('english', COALESCE(e.supplier_address, '') || ' ' || COALESCE(e.customer_address, '') || ' ' || COALESCE(items.desc_agg, '')), 'C') ||
                    setweight(to_tsvector('english', COALESCE(d.raw_text, '')), 'D')
                )
                FROM documents_invoiceextraction e
                LEFT JOIN (
                    SELECT extraction_id, string_agg(description, ' ') AS desc_agg
                    FROM documents_lineitem
                    GROUP BY extraction_id
                ) items ON items.extraction_id = e.id
                WHERE d.id = e.document_id;
            """)

            # 2. Backfill documents without an extraction
            cursor.execute("""
                UPDATE documents_document d
                SET search_vector = (
                    setweight(to_tsvector('english', COALESCE(d.filename, '')), 'A') ||
                    setweight(to_tsvector('english', COALESCE(d.raw_text, '')), 'D')
                )
                WHERE d.id NOT IN (
                    SELECT document_id FROM documents_invoiceextraction WHERE document_id IS NOT NULL
                );
            """)


def clear_search_vectors(apps, schema_editor):
    """Reverse migration: clears search_vector on rollback."""
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("UPDATE documents_document SET search_vector = NULL;")


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0002_postgres_fts_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="search_vector",
            field=SearchVectorField(blank=True, editable=False, null=True),
        ),
        migrations.AddIndex(
            model_name="document",
            index=GinIndex(fields=["search_vector"], name="doc_search_vector_gin"),
        ),
        migrations.RunPython(
            code=populate_search_vectors,
            reverse_code=clear_search_vectors,
        ),
    ]
