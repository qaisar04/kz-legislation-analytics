"""Static (matplotlib PNG) and interactive (Plotly HTML) figures for the report and slides."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px

from src import config

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3df"
DIVERGING = "RdBu_r"
DPI = 160
WIDE = (11, 4.5)

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "axes.edgecolor": GRID,
    "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED, "text.color": TEXT,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.spines.top": False,
    "axes.spines.right": False, "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
    "lines.linewidth": 2, "legend.frameon": False,
})


def save(fig, name: str) -> str:
    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = config.FIGURES_DIR / f"{name}.png"
    fig.tight_layout()
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return str(path)


def plot_yearly(yearly: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=WIDE)
    ax.bar(yearly["year"], yearly["acts"], color=SERIES[0], width=0.8, label="Acts adopted")
    ax.plot(yearly["year"], yearly["moving_avg_3y"], color=SERIES[1], label="3-year moving average")
    ax.set(title="Legal acts adopted per year (1992–2025)", xlabel="Year of adoption", ylabel="Acts")
    ax.legend(loc="upper left")
    return save(fig, "01_yearly_activity")


def plot_monthly_rolling(rolling: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=WIDE)
    ax.plot(rolling.index, rolling["acts"], color=SERIES[0], linewidth=1, alpha=0.6, label="Monthly acts")
    ax.plot(rolling.index, rolling["rolling_mean"], color=SERIES[1], label="12-month rolling mean")
    ax.set(title="Monthly legislative activity with 12-month rolling mean", xlabel="Month", ylabel="Acts")
    ax.legend(loc="upper left")
    return save(fig, "02_monthly_rolling")


def plot_decomposition(result) -> str:
    fig, axes = plt.subplots(4, 1, figsize=(11, 8), sharex=True)
    parts = [("Observed", result.observed), ("Trend", result.trend),
             ("Seasonal (multiplier)", result.seasonal), ("Residual", result.resid)]
    for ax, (label, series) in zip(axes, parts):
        ax.plot(series.index, series, color=SERIES[0], linewidth=1.5)
        ax.set_ylabel(label)
    axes[0].set_title("Multiplicative seasonal decomposition of monthly acts (2010–2025, period = 12)")
    return save(fig, "03_decomposition")


def plot_month_boxplot(monthly: pd.Series) -> str:
    frame = pd.DataFrame({"month": monthly.index.month, "acts": monthly.to_numpy()})
    frame = frame[monthly.index.year >= 2010]
    data = [frame.loc[frame["month"] == m, "acts"] for m in range(1, 13)]
    fig, ax = plt.subplots(figsize=WIDE)
    ax.boxplot(data, patch_artist=True, boxprops={"facecolor": "#cfe0f5", "color": SERIES[0]},
               medianprops={"color": SERIES[1], "linewidth": 2}, flierprops={"markeredgecolor": SERIES[7]})
    ax.set_xticks(range(1, 13), ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
                                  "Oct", "Nov", "Dec"])
    ax.set(title="Distribution of monthly act counts by calendar month (2010–2025, IQR boxplot)",
           ylabel="Acts per month")
    return save(fig, "04_month_boxplot")


def plot_authority_share(share: pd.DataFrame) -> str:
    pivot = share.pivot_table(index="year", columns="authority_level", values="share_pct", fill_value=0)
    order = pivot.sum().sort_values(ascending=False).index
    fig, ax = plt.subplots(figsize=WIDE)
    ax.stackplot(pivot.index, [pivot[c] for c in order], labels=order,
                 colors=SERIES[:len(order)], edgecolor=SURFACE, linewidth=0.5)
    ax.set(title="Share of acts by issuing authority level", xlabel="Year", ylabel="% of year's acts",
           ylim=(0, 100))
    ax.legend(loc="center left", bbox_to_anchor=(1, 0.5))
    return save(fig, "05_authority_share")


def plot_repeal_rate(yearly: pd.DataFrame) -> str:
    rate = 100 * yearly["repealed"] / yearly["acts"]
    fig, ax = plt.subplots(figsize=WIDE)
    ax.plot(yearly["year"], rate, color=SERIES[0], marker="o", markersize=4)
    ax.set(title="Share of acts already repealed, by year of adoption", xlabel="Year of adoption",
           ylabel="Repealed, %", ylim=(0, 100))
    return save(fig, "06_repeal_rate")


def plot_correlation(corr: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(9, 7))
    labels = [name[:28] + ("…" if len(name) > 28 else "") for name in corr.columns]
    image = ax.imshow(corr, cmap=DIVERGING, vmin=-1, vmax=1)
    ax.set_xticks(range(len(labels)), labels, rotation=45, ha="right")
    ax.set_yticks(range(len(labels)), labels)
    for i in range(len(corr)):
        for j in range(len(corr)):
            ax.text(j, i, f"{corr.iat[i, j]:.2f}", ha="center", va="center", fontsize=8, color=TEXT)
    ax.grid(False)
    fig.colorbar(image, ax=ax, label="Pearson r")
    ax.set_title("Correlation of yearly act counts across top database sections (2000–2025)")
    return save(fig, "07_correlation_heatmap")


def plot_forecast(train: pd.Series, predictions: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=WIDE)
    history = train[train.index >= "2019-01-01"]
    ax.plot(history.index, history, color=MUTED, linewidth=1.5, label="Train (actual)")
    ax.plot(predictions.index, predictions["actual"], color=TEXT, linewidth=2, label="Test (actual)")
    for color, column in zip(SERIES, [c for c in predictions.columns if c != "actual"]):
        ax.plot(predictions.index, predictions[column], color=color, linewidth=1.5, linestyle="--", label=column)
    ax.axvline(predictions.index[0], color=GRID, linewidth=1)
    ax.set(title="Forecast of monthly acts on the 2023–2025 hold-out", xlabel="Month", ylabel="Acts")
    ax.legend(loc="upper left", fontsize=8)
    return save(fig, "08_forecast")


def plot_missingness(missing: dict) -> str:
    series = pd.Series(missing).mul(100).sort_values()
    series = series[series > 0]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(series.index, series.values, color=SERIES[0], height=0.7)
    for y, value in enumerate(series.values):
        ax.text(value + 1, y, f"{value:.1f}%", va="center", fontsize=8, color=MUTED)
    ax.set(title="Missing values per field (after placeholder normalisation)", xlabel="% missing", xlim=(0, 110))
    return save(fig, "09_missingness")


def plot_top_areas(areas: pd.DataFrame, top_n: int = 12) -> str:
    top = areas.head(top_n).iloc[::-1]
    labels = [a[:45] + ("…" if len(a) > 45 else "") for a in top["area"]]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.barh(labels, top["acts"], color=SERIES[0], height=0.7)
    ax.set(title=f"Top {top_n} areas of legal regulation by number of acts", xlabel="Acts")
    return save(fig, "10_top_areas")


def plot_loading_benchmark(loading: list[dict]) -> str:
    frame = pd.DataFrame(loading).iloc[::-1]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
    axes[0].barh(frame["approach"], frame["seconds"], color=SERIES[0], height=0.6)
    axes[0].set(title="Load time, s", xlabel="seconds")
    axes[1].barh(frame["approach"], frame["peak_rss_mb"], color=SERIES[1], height=0.6)
    axes[1].set(title="Peak process memory, MB", xlabel="MB")
    return save(fig, "11_loading_benchmark")


def interactive_authority(share: pd.DataFrame) -> str:
    fig = px.area(share, x="year", y="acts", color="authority_level",
                  color_discrete_sequence=SERIES, title="Acts per year by issuing authority level")
    path = config.FIGURES_DIR / "interactive_authority.html"
    fig.write_html(path, include_plotlyjs="cdn")
    return str(path)
