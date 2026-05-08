import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE_PATH = ROOT_DIR / "database" / "traderoot.db"


def get_live_database_url() -> str:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        return database_url
    return f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"


def get_sqlite_db_path() -> str | None:
    database_url = get_live_database_url()
    if not database_url.startswith("sqlite:///"):
        return None
    return os.path.normpath(database_url.removeprefix("sqlite:///"))


def uses_sqlite() -> bool:
    return get_sqlite_db_path() is not None