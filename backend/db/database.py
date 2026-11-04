"""Local configuration; restoring an archive never silently loads its old .env."""
import os
from pathlib import Path
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

BASE_DIR = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv('DATABASE_URL', f"sqlite:///{(BASE_DIR / 'nba_local.db').as_posix()}")
if DATABASE_URL.startswith(('postgres://', 'postgresql://')):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql+psycopg://', 1).replace('postgresql://', 'postgresql+psycopg://', 1)
is_sqlite = DATABASE_URL.startswith('sqlite')
options = {'connect_args': {'check_same_thread': False, 'timeout': 15}} if is_sqlite else {'connect_args': {'connect_timeout': 10}, 'pool_timeout': 15}
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
    schema = inspect(engine)
    if schema.has_table('users'):
        if 'balance_cents' not in {c['name'] for c in schema.get_columns('users')}:
            raise RuntimeError('Legacy database: use scripts/migrate_legacy.py with a new destination; original data is preserved.')
    Base.metadata.create_all(engine)

def get_db():
    with SessionLocal() as db:
        try:
            if is_sqlite:
                db.execute(text('BEGIN IMMEDIATE'))
            yield db
        finally:
            db.rollback()  # every mutating endpoint commits before returning success
