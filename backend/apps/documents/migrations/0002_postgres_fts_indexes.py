"""
Migration adding PostgreSQL-specific Full-Text Search GIN indexes for Document model.
Applies:
- Functional GIN index on to_tsvector('english', COALESCE(raw_text, ''))
- Functional GIN index on to_tsvector('english', COALESCE(filename, ''))
Conditionally executes when connection.vendor == 'postgresql', ensuring full
compatibility and graceful execution across SQLite test workflows.
"""
from django.db import migrations


def create_postgres_gin_indexes(apps, schema_editor):
    """Creates PostgreSQL functional GIN indexes if connected to PostgreSQL."""
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS doc_raw_text_search_gin
                ON documents_document
                USING gin (to_tsvector('english', COALESCE(raw_text, '')));
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS doc_filename_search_gin
                ON documents_document
                USING gin (to_tsvector('english', COALESCE(filename, '')));
            """)


def remove_postgres_gin_indexes(apps, schema_editor):
    """Drops PostgreSQL functional GIN indexes on rollback."""
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("DROP INDEX IF EXISTS doc_raw_text_search_gin;")
            cursor.execute("DROP INDEX IF EXISTS doc_filename_search_gin;")


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            code=create_postgres_gin_indexes,
            reverse_code=remove_postgres_gin_indexes,
        ),
    ]
