"""Download the raw CSV, read it in chunks with optimised dtypes and persist it as Parquet."""
import time
import urllib.request

import pandas as pd

from src import config

BYTES_IN_MB = 1024 ** 2
LOW_CARDINALITY_RATIO = 0.5


def download_dataset(force: bool = False) -> bool:
    """Fetch the CSV from Hugging Face. Returns True when a download happened."""
    if config.RAW_CSV.exists() and not force:
        return False
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(config.DATASET_URL, config.RAW_CSV)
    return True


def memory_mb(df: pd.DataFrame) -> float:
    return round(df.memory_usage(deep=True).sum() / BYTES_IN_MB, 2)


def optimize_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    """Placeholders -> NaN, 't'/'f' -> bool, ISO strings -> datetime64, ids -> numeric."""
    chunk = chunk.replace(config.PLACEHOLDER_VALUES, pd.NA)
    for col in config.BOOL_COLUMNS:
        chunk[col] = chunk[col].eq(config.TRUE_FLAG)
    for col in config.DATE_COLUMNS:
        chunk[col] = pd.to_datetime(chunk[col], format=config.DATE_FORMAT, errors="coerce")
    chunk[config.COL_SOURCE_ID] = pd.to_numeric(chunk[config.COL_SOURCE_ID], downcast="integer")
    chunk[config.COL_STATE_REG_NUMBER] = pd.to_numeric(
        chunk[config.COL_STATE_REG_NUMBER], errors="coerce", downcast="float")
    return chunk


def to_categories(df: pd.DataFrame) -> pd.DataFrame:
    """Repeated strings become 'category' — applied after concat so codes are global."""
    for col in config.CATEGORY_COLUMNS:
        if df[col].nunique() / len(df) < LOW_CARDINALITY_RATIO:
            df[col] = df[col].astype("category")
    return df


def read_csv_chunked(path=config.RAW_CSV, chunksize: int = config.CHUNK_SIZE) -> pd.DataFrame:
    chunks = []
    for chunk in pd.read_csv(path, dtype=str, chunksize=chunksize,
                             keep_default_na=False, encoding=config.CSV_ENCODING):
        chunks.append(optimize_chunk(chunk))
    return to_categories(pd.concat(chunks, ignore_index=True))


def read_csv_naive(path=config.RAW_CSV) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, encoding=config.CSV_ENCODING)


def build_parquet() -> dict:
    """Chunked CSV -> optimised DataFrame -> Parquet. Returns timing/memory stats."""
    start = time.perf_counter()
    df = read_csv_chunked()
    elapsed = time.perf_counter() - start
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(config.PARQUET_FILE, index=False, compression="snappy")
    return {"rows": len(df), "columns": df.shape[1], "chunked_read_seconds": round(elapsed, 2),
            "optimized_memory_mb": memory_mb(df),
            "parquet_size_mb": round(config.PARQUET_FILE.stat().st_size / BYTES_IN_MB, 2)}


def load_acts() -> pd.DataFrame:
    if not config.PARQUET_FILE.exists():
        raise FileNotFoundError(f"{config.PARQUET_FILE} not found — run the ingest step first")
    return pd.read_parquet(config.PARQUET_FILE)
