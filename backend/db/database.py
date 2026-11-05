"""Local configuration; restoring an archive never silently loads its old .env."""
import os
from pathlib import Path
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

BASE_DIR = Path(__file__).resolve().parents[2]
if os.getenv('VERCEL') and not os.getenv('DATABASE_URL'):
    raise RuntimeError('Vercel requires an explicit PostgreSQL DATABASE_URL; local SQLite is disabled on hosted deployments.')
DATABASE_URL = os.getenv('DATABASE_URL', f"sqlite:///{(BASE_DIR / 'nba_local.db').as_posix()}")
if DATABASE_URL.startswith(('postgres://', 'postgresql://')):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql+psycopg://', 1).replace('postgresql://', 'postgresql+psycopg://', 1)
if DATABASE_URL.startswith('postgresql+psycopg2://'):
    DATABASE_URL = DATABASE_URL.replace('postgresql+psycopg2://', 'postgresql+psycopg://', 1)
dialect = make_url(DATABASE_URL).get_backend_name()
is_sqlite = dialect == 'sqlite'
if os.getenv('VERCEL') and is_sqlite:
    raise RuntimeError('SQLite cannot persist a deployed tournament. Configure PostgreSQL before deployment.')
if dialect not in ('sqlite', 'postgresql'):
    raise RuntimeError('DATABASE_URL must select SQLite or PostgreSQL.')
options = {'connect_args': {'check_same_thread': False, 'timeout': 15}} if is_sqlite else {
    'connect_args': {'connect_timeout': 10, 'prepare_threshold': None},
    'poolclass': NullPool,
}
if DATABASE_URL in ('sqlite://', 'sqlite:///:memory:'):
    options['poolclass'] = StaticPool
engine = create_engine(DATABASE_URL, pool_pre_ping=True, **options)
if is_sqlite:
    @event.listens_for(engine, 'connect')
    def sqlite_constraints(connection, _record):
        connection.execute('PRAGMA foreign_keys=ON')
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base = declarative_base()

def initialize_database():
    from backend.db import models  # noqa: F401
    with engine.begin() as connection:
        schema = inspect(connection)
        if schema.has_table('users') and 'balance_cents' not in {c['name'] for c in schema.get_columns('users')}:
            raise RuntimeError('Legacy database: an explicit reviewed migration is required; original data is preserved.')
        if is_sqlite:
            Base.metadata.create_all(connection)
            return
        # Production schema changes require an explicit reviewed migration. Never create
        # publicly exposed Supabase tables as a side effect of an HTTP request.
        expected = Base.metadata.tables
        if set(expected) - set(schema.get_table_names()):
            raise RuntimeError('PostgreSQL schema requires a reviewed migration before serving requests.')
        columns = schema.get_multi_columns(filter_names=list(expected))
        for name, table in expected.items():
            present = {column['name'] for column in columns.get((None, name), ())}
            if set(table.columns.keys()) - present:
                raise RuntimeError(f'PostgreSQL table {name} is missing application columns; apply the reviewed migration.')
        protected = set(connection.execute(text(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = current_schema() AND c.relrowsecurity"
        )).scalars())
        if not set(expected).issubset(protected):
            raise RuntimeError('Enable row level security on every application table before serving requests.')

def get_db():
    with SessionLocal() as db:
        try:
            if is_sqlite:
                db.execute(text('BEGIN IMMEDIATE'))
            yield db
        finally:
            db.rollback()  # every mutating endpoint commits before returning success
