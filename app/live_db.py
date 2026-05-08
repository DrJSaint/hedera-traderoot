from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.database_config import get_live_database_url


def normalise_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return "postgresql+psycopg://" + database_url[len("postgres://"):]
    if database_url.startswith("postgresql://") and "+" not in database_url.split("://", 1)[0]:
        return "postgresql+psycopg://" + database_url[len("postgresql://"):]
    return database_url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    database_url = normalise_database_url(get_live_database_url())
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite:///") else {}
    engine = create_engine(database_url, future=True, pool_pre_ping=True, connect_args=connect_args)
    if database_url.startswith("sqlite:///"):
        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.close()
    return engine