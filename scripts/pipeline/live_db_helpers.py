from sqlalchemy import text

from app.live_db import get_engine


ENGINE = get_engine()


def connect():
    return ENGINE.connect()


def begin():
    return ENGINE.begin()


def fetch_all(conn, query: str, params: dict | None = None) -> list[dict]:
    return [dict(row) for row in conn.execute(text(query), params or {}).mappings().all()]


def fetch_one(conn, query: str, params: dict | None = None) -> dict | None:
    row = conn.execute(text(query), params or {}).mappings().first()
    return dict(row) if row else None


def fetch_scalar(conn, query: str, params: dict | None = None):
    return conn.execute(text(query), params or {}).scalar()


def execute(conn, query: str, params: dict | None = None):
    return conn.execute(text(query), params or {})


def insert_ignore_sql(table: str, columns: list[str], conflict_columns: list[str]) -> str:
    column_list = ", ".join(columns)
    value_list = ", ".join(f":{column}" for column in columns)
    if ENGINE.dialect.name == "postgresql":
        conflicts = ", ".join(conflict_columns)
        return (
            f"INSERT INTO {table} ({column_list}) VALUES ({value_list}) "
            f"ON CONFLICT ({conflicts}) DO NOTHING"
        )
    return f"INSERT OR IGNORE INTO {table} ({column_list}) VALUES ({value_list})"


def group_concat_sql(column: str, separator: str = ",", distinct: bool = False) -> str:
    if ENGINE.dialect.name == "postgresql":
        distinct_sql = "DISTINCT " if distinct else ""
        return f"string_agg({distinct_sql}{column}, '{separator}')"
    distinct_sql = "DISTINCT " if distinct else ""
    if separator == ",":
        return f"GROUP_CONCAT({distinct_sql}{column})"
    return f"GROUP_CONCAT({distinct_sql}{column}, '{separator}')"