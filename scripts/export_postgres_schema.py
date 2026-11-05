"""Print a PostgreSQL schema plan. Never connects to, reads, or changes a database.

This initializes an empty/new schema only. An existing legacy database needs a
separate data-preserving migration after its actual columns have been inspected.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Import metadata without allowing environment credentials to select a remote DB.
os.environ.pop('VERCEL', None)
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

from sqlalchemy.dialects.postgresql import dialect
from sqlalchemy.schema import CreateIndex, CreateTable
from backend.db.models import Base


def schema_plan():
    pg = dialect()
    quote = pg.identifier_preparer.quote
    commands = [
        '-- REVIEW BEFORE APPLYING. Legacy data must be migrated separately.',
        'BEGIN;',
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = current_schema() AND table_name = 'users') "
        "AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = 'users' AND column_name = 'balance_cents') "
        "THEN RAISE EXCEPTION 'Legacy users table detected. No changes applied; review a data-preserving migration first.'; END IF; END $$;",
    ]
    for table in Base.metadata.sorted_tables:
        commands.append(str(CreateTable(table, if_not_exists=True).compile(dialect=pg)).strip() + ';')
        for index in sorted(table.indexes, key=lambda item: item.name):
            commands.append(str(CreateIndex(index, if_not_exists=True).compile(dialect=pg)).strip() + ';')
        name = quote(table.name)
        commands.append(f'ALTER TABLE {name} ENABLE ROW LEVEL SECURITY;')
        commands.append(f'REVOKE ALL ON TABLE {name} FROM PUBLIC;')
        for role in ('anon', 'authenticated'):
            commands.append(
                f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') "
                f'THEN REVOKE ALL ON TABLE {name} FROM {role}; END IF; END $$;'
            )
    commands.append('COMMIT;')
    return '\n\n'.join(commands) + '\n'


if __name__ == '__main__':
    print(schema_plan(), end='')
