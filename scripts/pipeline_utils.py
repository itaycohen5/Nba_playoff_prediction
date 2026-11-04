"""Shared validation and atomic output helpers for optional offline tools."""
from pathlib import Path
import os
import tempfile
import time

BASE = Path(__file__).resolve().parent.parent


def atomic_csv(frame, target):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=target.stem + "-", suffix=".tmp", dir=target.parent)
    os.close(fd)
    try:
        frame.to_csv(name, index=False)
        os.replace(name, target)
    finally:
        Path(name).unlink(missing_ok=True)


def nba_request(endpoint, **kwargs):
    # Bounded retries and per-attempt timeout; never runs during app startup.
    for attempt in range(3):
        try:
            return endpoint(timeout=30, **kwargs).get_data_frames()[0]
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def require_columns(frame, columns):
    missing = set(columns) - set(frame.columns)
    if missing or frame.empty:
        raise ValueError(f"Missing data or columns: {sorted(missing)}")
