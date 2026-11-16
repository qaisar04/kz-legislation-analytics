"""Cluster-1 time-series tasks: monthly series, resampling, rolling means, seasonal
decomposition and a leakage-free (time-ordered) forecast comparison against naive baselines."""
import time

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error
from statsmodels.tsa.seasonal import seasonal_decompose

from src import config

MONTH_START = "MS"
YEAR_START = "YS"


def monthly_counts(acts: pd.DataFrame) -> pd.Series:
    """Acts per month over full years only (the source stops mid-2026)."""
    series = acts.set_index(config.COL_DATE_ADOPTED).resample(MONTH_START).size()
    in_range = (series.index.year >= config.FIRST_FULL_YEAR) & (series.index.year <= config.LAST_FULL_YEAR)
    return series[in_range].rename("acts")


def resample_views(monthly: pd.Series) -> pd.DataFrame:
    yearly = monthly.resample(YEAR_START).sum()
    return pd.DataFrame({"acts": yearly, "pct_change": yearly.pct_change().round(3)})


def with_rolling(monthly: pd.Series, window: int = config.ROLLING_WINDOW) -> pd.DataFrame:
    return pd.DataFrame({"acts": monthly,
                         "rolling_mean": monthly.rolling(window).mean(),
                         "rolling_std": monthly.rolling(window).std()})


def decompose(monthly: pd.Series, start_year: int = 2010):
    """Multiplicative: seasonal swings grow with the level of activity."""
    return seasonal_decompose(monthly[monthly.index.year >= start_year],
                              model="multiplicative", period=config.SEASONAL_PERIOD)


def describe_with_outliers(monthly: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Descriptive statistics + months outside the 1.5*IQR fences."""
    q1, q3 = monthly.quantile([0.25, 0.75])
    iqr = q3 - q1
    outliers = monthly[(monthly < q1 - 1.5 * iqr) | (monthly > q3 + 1.5 * iqr)]
    return monthly.describe().round(1), outliers


def split_train_test(monthly: pd.Series, test_start: str = config.FORECAST_TEST_START):
    return monthly[monthly.index < test_start], monthly[monthly.index >= test_start]


def forecast_naive(train: pd.Series, horizon: int) -> np.ndarray:
    return np.repeat(train.iloc[-1], horizon)


def forecast_seasonal_naive(train: pd.Series, horizon: int) -> np.ndarray:
    last_season = train.iloc[-config.SEASONAL_PERIOD:].to_numpy()
    return np.resize(last_season, horizon)


def forecast_moving_average(train: pd.Series, horizon: int) -> np.ndarray:
    return np.repeat(train.iloc[-config.ROLLING_WINDOW:].mean(), horizon)


def calendar_features(index: pd.DatetimeIndex, origin: pd.Timestamp) -> pd.DataFrame:
    features = {f"m_{m}": (index.month == m).astype(int) for m in range(2, 13)}
    features["trend"] = (index.year - origin.year) * 12 + (index.month - origin.month)
    return pd.DataFrame(features, index=index)


def forecast_linear(train: pd.Series, test_index: pd.DatetimeIndex, fit_from: str = "2014-01-01") -> np.ndarray:
    """Trend + month dummies; fitted on the recent regime only (volume level shifted ~2014-2015)."""
    recent = train[train.index >= fit_from]
    origin = recent.index[0]
    model = LinearRegression().fit(calendar_features(recent.index, origin), recent.to_numpy())
    return np.clip(model.predict(calendar_features(test_index, origin)), 0, None)


def compare_forecasts(monthly: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (metrics table, predictions frame) for all methods on the hold-out years."""
    train, test = split_train_test(monthly)
    methods = {
        "naive (baseline)": lambda: forecast_naive(train, len(test)),
        "seasonal naive": lambda: forecast_seasonal_naive(train, len(test)),
        "moving average 12m": lambda: forecast_moving_average(train, len(test)),
        "linear regression (trend+month)": lambda: forecast_linear(train, test.index),
    }
    rows, predictions = [], {"actual": test.to_numpy()}
    for name, method in methods.items():
        start = time.perf_counter()
        predicted = method()
        elapsed_ms = (time.perf_counter() - start) * 1000
        predictions[name] = predicted
        rows.append({"method": name, "MAE": round(mean_absolute_error(test, predicted), 1),
                     "MAPE_pct": round(float(np.mean(np.abs(test - predicted) / test)) * 100, 1),
                     "fit_predict_ms": round(elapsed_ms, 2)})
    metrics = pd.DataFrame(rows).sort_values("MAE").reset_index(drop=True)
    return metrics, pd.DataFrame(predictions, index=test.index)


def correlation_matrix(acts: pd.DataFrame, top_n: int = 8) -> pd.DataFrame:
    """Correlation of yearly act counts across the busiest database sections."""
    years = acts[config.COL_DATE_ADOPTED].dt.year
    in_range = years.between(2000, config.LAST_FULL_YEAR)
    subset = acts.loc[in_range, [config.COL_SECTION]].assign(year=years[in_range])
    top = subset[config.COL_SECTION].value_counts().head(top_n).index
    pivot = (subset[subset[config.COL_SECTION].isin(top)]
             .pivot_table(index="year", columns=config.COL_SECTION, aggfunc="size", observed=True))
    return pivot.corr().round(2)
