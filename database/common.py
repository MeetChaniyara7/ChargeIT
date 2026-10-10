"""Connection helpers shared by the migration runner, import scripts, seeds and tests.

Database URLs live in backend/.env (never in code):
    DATABASE_URL         the real database (Supabase)
    LEGACY_DATABASE_URL  the old local database, read once to copy users
    TEST_DATABASE_URL    a throwaway local database that tests wipe
"""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
LEGACY_DIR = DATA_DIR / "legacy"

load_dotenv(REPO_ROOT / "backend" / ".env")


def database_url(env_name: str = "DATABASE_URL") -> str:
    """Read a database URL from the environment, in the plain form psycopg expects."""
    url = os.getenv(env_name, "").strip().strip("\"'")
    if not url:
        raise SystemExit(f"{env_name} is not set. Add it to backend/.env (see backend/.env.example).")
    # The API uses SQLAlchemy's "postgresql+psycopg://" prefix; psycopg wants "postgresql://".
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def connect(env_name: str = "DATABASE_URL", **kwargs) -> psycopg.Connection:
    return psycopg.connect(database_url(env_name), connect_timeout=15, **kwargs)
