"""Metadata quality audit over the raw CSV (chunked) and the optimised Parquet."""
import json
import re

import pandas as pd

from src import config
from src.normalize import split_multi_value

ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TOP_N = 10


def count_raw_issues(path=config.RAW_CSV) -> dict:
    """Per column: empty strings, explicit placeholders and non-ISO dates in the raw text."""
    stats = {}
    for chunk in pd.read_csv(path, dtype=str, chunksize=config.CHUNK_SIZE, keep_default_na=False):
        for col in chunk.columns:
            col_stats = stats.setdefault(col, {"empty": 0, "placeholder": 0, "bad_date": 0})
            values = chunk[col].str.strip()
            col_stats["empty"] += int(values.eq("").sum())
            col_stats["placeholder"] += int(values.isin(config.SOURCE_PLACEHOLDERS).sum())
            if col in config.DATE_COLUMNS:
                filled = values[values.ne("")]
                col_stats["bad_date"] += int((~filled.str.match(ISO_DATE_PATTERN)).sum())
    return stats


def missing_share(df: pd.DataFrame) -> dict:
    return df.isna().mean().round(4).sort_values(ascending=False).to_dict()


def multi_value_profile(df: pd.DataFrame) -> dict:
    profile = {}
    for col in config.MULTI_VALUE_COLUMNS:
        items = split_multi_value(df[col], col)
        counts = items.map(len)
        profile[col] = {"multi_value_share": round(float((counts > 1).mean()), 4),
                        "max_values_per_act": int(counts.max()),
                        "distinct_values": int(items.explode().nunique())}
    return profile


def consistency_checks(df: pd.DataFrame) -> dict:
    adopted = df[config.COL_DATE_ADOPTED]
    return {
        "constant_columns": [c for c in df.columns if df[c].nunique(dropna=True) <= 1],
        "duplicate_law_id": int(df[config.COL_LAW_ID].duplicated().sum()),
        "duplicate_titles": int(df[config.COL_TITLE].duplicated().sum()),
        "modified_before_adopted": int((df[config.COL_DATE_MODIFIED] < adopted).sum()),
        "published_before_adopted": int((df[config.COL_DATE_PUBLISHED] < adopted).sum()),
        "date_adopted_min": str(adopted.min().date()),
        "date_adopted_max": str(adopted.max().date()),
        "repealed_share": round(float(df[config.COL_IS_REPEALED].mean()), 4),
    }


def run_audit(df: pd.DataFrame) -> dict:
    report = {"raw_issues": count_raw_issues(), "missing_share": missing_share(df),
              "multi_value": multi_value_profile(df), "consistency": consistency_checks(df)}
    config.TABLES_DIR.mkdir(parents=True, exist_ok=True)
    config.AUDIT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
