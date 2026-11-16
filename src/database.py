"""SQLite layer: create schema, bulk-load normalised tables, run named queries into Pandas.

Contract: load_database(tables) expects the dict produced by normalize.build_tables;
run_query(name) returns a DataFrame for a key of queries.QUERIES.
"""
import sqlite3
from contextlib import closing

import pandas as pd

from src import config
from src.queries import QUERIES

LOAD_ORDER = ["body", "region", "legal_force", "section", "area", "form", "act", "act_area", "act_form"]
INSERT_CHUNK = 20_000


class UnknownQueryError(KeyError):
    """Raised when a query name is not defined in queries.QUERIES."""


def connect(db_path=config.DB_FILE) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(f"{db_path} not found — run the database build step first")
    return sqlite3.connect(db_path)


def load_database(tables: dict, db_path=config.DB_FILE) -> dict:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db_path)) as conn:
        conn.executescript(config.SCHEMA_FILE.read_text(encoding="utf-8"))
        for name in LOAD_ORDER:
            tables[name].to_sql(name, conn, if_exists="append", index=False, chunksize=INSERT_CHUNK)
        conn.commit()
        counts = {n: conn.execute(f"SELECT COUNT(*) FROM {n}").fetchone()[0] for n in LOAD_ORDER}
    return counts


def run_query(name: str, params: tuple = ()) -> pd.DataFrame:
    if name not in QUERIES:
        raise UnknownQueryError(f"Unknown query '{name}'. Available: {', '.join(QUERIES)}")
    with closing(connect()) as conn:
        return pd.read_sql_query(QUERIES[name]["sql"], conn, params=params)


def run_sql(sql: str, params: tuple = ()) -> pd.DataFrame:
    with closing(connect()) as conn:
        return pd.read_sql_query(sql, conn, params=params)


def export_all_queries() -> dict:
    """Runs every named query and saves it as CSV. Returns {name: row_count}."""
    config.QUERY_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    summary = {}
    for name in QUERIES:
        result = run_query(name)
        result.to_csv(config.QUERY_RESULTS_DIR / f"{name}.csv", index=False)
        summary[name] = len(result)
    return summary
