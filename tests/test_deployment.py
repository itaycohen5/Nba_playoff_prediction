"""Deployment guards are checked in isolated processes without remote credentials."""
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.db.auth import auth_settings

ROOT = Path(__file__).resolve().parents[1]


def test_vercel_refuses_missing_database_configuration():
    environment = dict(os.environ, VERCEL='1')
    environment.pop('DATABASE_URL', None)
    result = subprocess.run([sys.executable, '-c', 'import backend.db.database'],
                            cwd=ROOT, env=environment, capture_output=True, text=True)
    assert result.returncode != 0
    assert 'requires an explicit PostgreSQL DATABASE_URL' in result.stderr


def test_vercel_refuses_ephemeral_sqlite():
    environment = dict(os.environ, VERCEL='1', DATABASE_URL='sqlite:///:memory:')
    result = subprocess.run([sys.executable, '-c', 'import backend.db.database'],
                            cwd=ROOT, env=environment, capture_output=True, text=True)
    assert result.returncode != 0
    assert 'SQLite cannot persist a deployed tournament' in result.stderr


def test_vercel_rejects_other_database_dialects_before_loading_the_driver():
    environment = dict(os.environ, VERCEL='1', DATABASE_URL='mysql://invalid.invalid/nonexistent')
    result = subprocess.run([sys.executable, '-c', 'import backend.db.database'],
                            cwd=ROOT, env=environment, capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert 'DATABASE_URL must select SQLite or PostgreSQL' in result.stderr


def test_schema_export_is_offline_and_protects_all_application_tables():
    # Even a remote-looking credential must never be used by this export command.
    environment = dict(os.environ, VERCEL='1', DATABASE_URL='postgresql://invalid.invalid/nonexistent')
    result = subprocess.run([sys.executable, 'scripts/export_postgres_schema.py'],
                            cwd=ROOT, env=environment, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    for table in ('users', 'auth_sessions', 'account_emails', 'login_attempts', 'tournaments', 'mutations', 'bets', 'game_history'):
        assert f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;' in result.stdout
        assert f'REVOKE ALL ON TABLE {table} FROM PUBLIC;' in result.stdout
        assert f'REVOKE ALL ON TABLE {table} FROM anon;' in result.stdout
        assert f'REVOKE ALL ON TABLE {table} FROM authenticated;' in result.stdout
    assert 'Legacy users table detected' in result.stdout
    assert 'DROP TABLE' not in result.stdout


def test_hosted_auth_enforces_secure_cookies_and_explicit_origins():
    with patch.dict(os.environ, VERCEL='1', COOKIE_SECURE='false', APP_ORIGINS='https://playoff.example'):
        assert auth_settings() == (True, ['https://playoff.example'])

    with patch.dict(os.environ, APP_ORIGINS='*'):
        with pytest.raises(RuntimeError, match='must list explicit origins'):
            auth_settings()
