"""Requirement 9: compare storage formats (CSV vs Parquet) and engines (Pandas vs SQL)
by execution time and memory, and check that both engines give identical answers.

Each loader runs in its own subprocess so peak RSS (which includes Arrow buffers that
tracemalloc cannot see) is measured per approach rather than accumulated."""
import json
import os
import statistics
import subprocess
import sys
import time

import pandas as pd

from src import config, ingest
from src.database import run_sql
from src.normalize import split_multi_value

ANALYSIS_COLUMNS = [config.COL_DATE_ADOPTED, config.COL_IS_REPEALED, config.COL_LEGAL_FORCE, config.COL_AREA]
TIMING_REPEATS = 5
MACOS_RSS_UNIT = 1
LINUX_RSS_UNIT = 1024

LOADERS = {
    "CSV, object dtype (baseline)": lambda: pd.read_csv(config.RAW_CSV, dtype=object),
    "CSV, default pandas dtypes": lambda: pd.read_csv(config.RAW_CSV, low_memory=False),
    "CSV, chunked + optimised dtypes": ingest.read_csv_chunked,
    "Parquet, all columns": lambda: pd.read_parquet(config.PARQUET_FILE),
    "Parquet, 4 analysis columns": lambda: pd.read_parquet(config.PARQUET_FILE, columns=ANALYSIS_COLUMNS),
}


def run_loader(name: str) -> None:
    """Child-process entry point: prints JSON with time and DataFrame size."""
    start = time.perf_counter()
    df = LOADERS[name]()
    print(json.dumps({"seconds": round(time.perf_counter() - start, 2), "dataframe_mb": ingest.memory_mb(df)}))


def peak_rss_mb(rusage) -> float:
    unit = MACOS_RSS_UNIT if sys.platform == "darwin" else LINUX_RSS_UNIT
    return round(rusage.ru_maxrss * unit / ingest.BYTES_IN_MB, 1)


def benchmark_loading() -> list[dict]:
    rows = []
    for name in LOADERS:
        proc = subprocess.Popen([sys.executable, "-m", "src.benchmark", name],
                                cwd=config.ROOT_DIR, stdout=subprocess.PIPE, text=True)
        output = proc.stdout.read()
        _, _, rusage = os.wait4(proc.pid, 0)
        rows.append({"approach": name, **json.loads(output), "peak_rss_mb": peak_rss_mb(rusage)})
    return rows


def median_seconds(func) -> tuple[object, float]:
    timings, result = [], None
    for _ in range(TIMING_REPEATS):
        start = time.perf_counter()
        result = func()
        timings.append(time.perf_counter() - start)
    return result, round(statistics.median(timings) * 1000, 1)


def pandas_tasks(acts: pd.DataFrame) -> dict:
    return {
        "yearly_counts": lambda: acts[config.COL_DATE_ADOPTED].dt.year.value_counts().sort_index(),
        "repeal_rate_by_force": lambda: acts.groupby(config.COL_LEGAL_FORCE, observed=True)[
            config.COL_IS_REPEALED].mean().sort_values(),
        "top_areas": lambda: split_multi_value(acts[config.COL_AREA], config.COL_AREA)
        .explode().value_counts().head(10),
    }


SQL_TASKS = {
    "yearly_counts": "SELECT adoption_year, COUNT(*) FROM act GROUP BY adoption_year ORDER BY 1",
    "repeal_rate_by_force": """SELECT lf.name, AVG(a.is_repealed) FROM act a
        JOIN legal_force lf ON lf.legal_force_id = a.legal_force_id GROUP BY lf.legal_force_id ORDER BY 2""",
    "top_areas": """SELECT ar.name, COUNT(*) FROM act_area aa JOIN area ar ON ar.area_id = aa.area_id
        GROUP BY aa.area_id ORDER BY 2 DESC LIMIT 10""",
}


def benchmark_engines() -> list[dict]:
    acts = ingest.load_acts()
    rows = []
    for task, pandas_func in pandas_tasks(acts).items():
        pd_result, pd_ms = median_seconds(pandas_func)
        sql_result, sql_ms = median_seconds(lambda: run_sql(SQL_TASKS[task]))
        rows.append({"task": task, "pandas_ms": pd_ms, "sqlite_ms": sql_ms,
                     "same_row_count": len(pd_result) == len(sql_result)})
    return rows


def run_benchmarks() -> dict:
    results = {"loading": benchmark_loading(), "engines": benchmark_engines(),
               "file_sizes_mb": {"csv": round(config.RAW_CSV.stat().st_size / ingest.BYTES_IN_MB, 1),
                                 "parquet": round(config.PARQUET_FILE.stat().st_size / ingest.BYTES_IN_MB, 1),
                                 "sqlite": round(config.DB_FILE.stat().st_size / ingest.BYTES_IN_MB, 1)}}
    config.TABLES_DIR.mkdir(parents=True, exist_ok=True)
    config.BENCHMARK_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results


if __name__ == "__main__":
    run_loader(sys.argv[1])
