"""End-to-end steps. Each step reads the artefacts of the previous one from disk,
so any step can be re-run on its own from the console menu."""
import json

import pandas as pd

from src import audit, benchmark, config, database, ingest, normalize, plots
from src import timeseries as ts


def step_ingest() -> dict:
    downloaded = ingest.download_dataset()
    return {"downloaded": downloaded, **ingest.build_parquet()}


def step_audit() -> dict:
    report = audit.run_audit(ingest.load_acts())
    plots.plot_missingness(report["missing_share"])
    return report["consistency"] | {"multi_value": report["multi_value"]}


def step_database() -> dict:
    counts = database.load_database(normalize.build_tables(ingest.load_acts()))
    return {"row_counts": counts, "query_rows": database.export_all_queries()}


def step_timeseries() -> dict:
    acts = ingest.load_acts()
    monthly = ts.monthly_counts(acts)
    stats, outliers = ts.describe_with_outliers(monthly)
    metrics, predictions = ts.compare_forecasts(monthly)
    train, _ = ts.split_train_test(monthly)
    metrics.to_csv(config.FORECAST_FILE, index=False)
    ts.resample_views(monthly).to_csv(config.TABLES_DIR / "yearly_resampled.csv")
    plots.plot_monthly_rolling(ts.with_rolling(monthly))
    plots.plot_decomposition(ts.decompose(monthly))
    plots.plot_month_boxplot(monthly)
    plots.plot_correlation(ts.correlation_matrix(acts))
    plots.plot_forecast(train, predictions)
    return {"monthly_stats": stats.to_dict(), "iqr_outlier_months": [str(d.date()) for d in outliers.index],
            "forecast": metrics.to_dict(orient="records")}


def step_sql_figures() -> list[str]:
    yearly = database.run_query("yearly_activity")
    yearly = yearly[yearly["year"].between(config.FIRST_FULL_YEAR, config.LAST_FULL_YEAR)]
    share = database.run_query("authority_share_by_year")
    share = share[share["year"] <= config.LAST_FULL_YEAR]
    return [plots.plot_yearly(yearly), plots.plot_repeal_rate(yearly), plots.plot_authority_share(share),
            plots.plot_top_areas(database.run_query("areas_repeal_rate")), plots.interactive_authority(share)]


def step_benchmark() -> dict:
    results = benchmark.run_benchmarks()
    plots.plot_loading_benchmark(results["loading"])
    return results


STEPS = {"ingest": step_ingest, "audit": step_audit, "database": step_database,
         "timeseries": step_timeseries, "sql_figures": step_sql_figures, "benchmark": step_benchmark}


def run_all() -> dict:
    summary = {}
    for name, step in STEPS.items():
        print(f"[pipeline] {name} ...", flush=True)
        summary[name] = step()
    (config.TABLES_DIR / "pipeline_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return summary
