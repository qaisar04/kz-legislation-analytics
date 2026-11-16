"""Interactive console menu for the Kazakhstan Legislation Analytics project."""
import sqlite3
import sys

import pandas as pd

from src import config, database, pipeline
from src.queries import QUERIES

MENU = {
    "1": ("Run full pipeline (download -> parquet -> audit -> SQLite -> analysis -> benchmarks)", None),
    "2": ("Load data: chunked CSV -> optimised Parquet", "ingest"),
    "3": ("Metadata quality audit", "audit"),
    "4": ("Build normalised SQLite database + export all SQL queries", "database"),
    "5": ("Time series: decomposition, IQR outliers, forecast comparison", "timeseries"),
    "6": ("Benchmarks: CSV vs Parquet, Pandas vs SQL", "benchmark"),
    "7": ("Run one analytical SQL query", None),
    "8": ("Search acts by keyword in the title", None),
    "0": ("Exit", None),
}
SEARCH_LIMIT = 15
MIN_KEYWORD_LENGTH = 3
SEARCH_SQL = """
SELECT a.date_adopted, a.is_repealed, lf.authority_level, a.title
FROM act a LEFT JOIN legal_force lf ON lf.legal_force_id = a.legal_force_id
WHERE a.title LIKE ? AND a.adoption_year BETWEEN ? AND ?
ORDER BY a.date_adopted DESC LIMIT ?"""

pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 90)


def print_menu() -> None:
    print("\n=== Kazakhstan Legislation Analytics ===")
    for key, (label, _) in MENU.items():
        print(f" {key} - {label}")


def ask_int(prompt: str, default: int) -> int:
    raw = input(f"{prompt} [{default}]: ").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"'{raw}' is not a number, using {default}")
        return default


def choose_query() -> None:
    names = list(QUERIES)
    for i, name in enumerate(names, start=1):
        print(f" {i:2d}. {name} — {QUERIES[name]['description']}")
    index = ask_int("Query number", 1)
    if not 1 <= index <= len(names):
        print("No such query.")
        return
    print(database.run_query(names[index - 1]).head(30).to_string(index=False))


def search_titles() -> None:
    keyword = input("Keyword (Kazakh, e.g. 'бюджет'): ").strip()
    if len(keyword) < MIN_KEYWORD_LENGTH:
        print(f"Please enter at least {MIN_KEYWORD_LENGTH} characters.")
        return
    year_from = ask_int("From year", config.FIRST_FULL_YEAR)
    year_to = ask_int("To year", config.LAST_FULL_YEAR + 1)
    result = database.run_sql(SEARCH_SQL, (f"%{keyword}%", year_from, year_to, SEARCH_LIMIT))
    print(result.to_string(index=False) if len(result) else "Nothing found.")


def run_step(key: str) -> None:
    label, step = MENU[key]
    if key == "1":
        pipeline.run_all()
    elif key == "7":
        choose_query()
    elif key == "8":
        search_titles()
    else:
        result = pipeline.STEPS[step]()
        print(pd.Series(result).to_string() if isinstance(result, dict) else result)
    print(f"Done: {label}")


def main() -> None:
    while True:
        print_menu()
        choice = input("Choose an option: ").strip()
        if choice == "0":
            print("Bye!")
            break
        if choice not in MENU:
            print("Unknown option, try again.")
            continue
        try:
            run_step(choice)
        except FileNotFoundError as error:
            print(f"Missing artefact: {error}. Run option 1 or 2 first.")
        except (sqlite3.Error, database.UnknownQueryError) as error:
            print(f"Database error: {error}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        pipeline.run_all()
    else:
        main()
