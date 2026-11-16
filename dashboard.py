"""Streamlit mini-dashboard: legislative activity with year / authority / region / form filters.
Run: streamlit run dashboard.py"""
import sqlite3
from contextlib import closing

import pandas as pd
import plotly.express as px
import streamlit as st

from src import config
from src.plots import SERIES

REPEAL_OPTIONS = {"All": None, "In force": 0, "Repealed": 1}
TOP_N = 10
ROLLING_MONTHS = 12

BASE_FROM = """
FROM act a
JOIN legal_force lf ON lf.legal_force_id = a.legal_force_id
JOIN region r ON r.region_id = a.region_id
LEFT JOIN body b ON b.body_id = a.body_id
"""


@st.cache_data
def read_sql(sql: str, params: tuple = ()) -> pd.DataFrame:
    with closing(sqlite3.connect(config.DB_FILE)) as conn:
        return pd.read_sql_query(sql, conn, params=params)


def options(sql: str) -> list:
    return read_sql(sql).iloc[:, 0].tolist()


def build_filters() -> tuple[str, tuple]:
    """Sidebar widgets -> parameterised WHERE clause (values never interpolated into SQL)."""
    st.sidebar.header("Filters")
    years = st.sidebar.slider("Year of adoption", config.FIRST_FULL_YEAR, 2026, (2000, config.LAST_FULL_YEAR))
    authorities = st.sidebar.multiselect(
        "Authority level", options("SELECT DISTINCT authority_level FROM legal_force ORDER BY 1"))
    levels = st.sidebar.multiselect("Territorial level", options("SELECT DISTINCT region_level FROM region ORDER BY 1"))
    region = st.sidebar.selectbox("Region", ["All"] + options(
        "SELECT short_name FROM region WHERE region_level IN ('oblast','city','national') ORDER BY 1"))
    form = st.sidebar.selectbox("Act form", ["All"] + options("SELECT name FROM form ORDER BY 1"))
    repeal = st.sidebar.radio("Status", list(REPEAL_OPTIONS), horizontal=True)

    clauses, params = ["a.adoption_year BETWEEN ? AND ?"], [years[0], years[1]]
    for column, values in (("lf.authority_level", authorities), ("r.region_level", levels)):
        if values:
            clauses.append(f"{column} IN ({','.join('?' * len(values))})")
            params.extend(values)
    if region != "All":
        clauses.append("r.short_name = ?")
        params.append(region)
    if form != "All":
        clauses.append("a.act_id IN (SELECT af.act_id FROM act_form af JOIN form f ON f.form_id = af.form_id "
                       "WHERE f.name = ?)")
        params.append(form)
    if REPEAL_OPTIONS[repeal] is not None:
        clauses.append("a.is_repealed = ?")
        params.append(REPEAL_OPTIONS[repeal])
    return " WHERE " + " AND ".join(clauses), tuple(params)


def show_kpis(where: str, params: tuple) -> None:
    kpi = read_sql(f"SELECT COUNT(*) acts, ROUND(100.0*AVG(a.is_repealed),1) repeal_pct, "
                   f"COUNT(DISTINCT a.body_id) bodies {BASE_FROM}{where}", params).iloc[0]
    cols = st.columns(3)
    cols[0].metric("Acts", f"{int(kpi['acts']):,}")
    cols[1].metric("Repealed", f"{kpi['repeal_pct'] or 0}%")
    cols[2].metric("Adopting bodies", f"{int(kpi['bodies']):,}")


def show_trends(where: str, params: tuple) -> None:
    yearly = read_sql(f"SELECT a.adoption_year year, lf.authority_level, COUNT(*) acts {BASE_FROM}{where} "
                      "GROUP BY 1, 2 ORDER BY 1", params)
    st.plotly_chart(px.bar(yearly, x="year", y="acts", color="authority_level",
                           color_discrete_sequence=SERIES, title="Acts per year by authority level"),
                    width="stretch")
    monthly = read_sql(f"SELECT substr(a.date_adopted,1,7) month, COUNT(*) acts {BASE_FROM}{where} "
                       "GROUP BY 1 ORDER BY 1", params)
    monthly["acts"] = monthly["acts"].astype(float)
    monthly["rolling_12m"] = monthly["acts"].rolling(ROLLING_MONTHS).mean()
    st.plotly_chart(px.line(monthly, x="month", y=["acts", "rolling_12m"], color_discrete_sequence=SERIES,
                            title="Monthly acts and 12-month rolling mean"), width="stretch")


def show_rankings(where: str, params: tuple) -> None:
    left, right = st.columns(2)
    bodies = read_sql(f"SELECT b.short_name body, COUNT(*) acts {BASE_FROM}{where} "
                      f"GROUP BY a.body_id ORDER BY acts DESC LIMIT {TOP_N}", params)
    left.plotly_chart(px.bar(bodies.iloc[::-1], x="acts", y="body", orientation="h",
                             color_discrete_sequence=SERIES, title="Top adopting bodies"), width="stretch")
    areas = read_sql(f"SELECT ar.name area, COUNT(*) acts {BASE_FROM} JOIN act_area aa ON aa.act_id = a.act_id "
                     f"JOIN area ar ON ar.area_id = aa.area_id {where} GROUP BY ar.area_id "
                     f"ORDER BY acts DESC LIMIT {TOP_N}", params)
    areas["area"] = areas["area"].str.slice(0, 50)
    right.plotly_chart(px.bar(areas.iloc[::-1], x="acts", y="area", orientation="h",
                              color_discrete_sequence=SERIES, title="Top regulation areas"), width="stretch")


def show_table(where: str, params: tuple) -> None:
    st.subheader("Latest acts")
    st.dataframe(read_sql(f"SELECT a.date_adopted, a.title, lf.authority_level, r.short_name region, "
                          f"a.is_repealed, a.adilet_url {BASE_FROM}{where} ORDER BY a.date_adopted DESC LIMIT 200",
                          params), width="stretch")


def main() -> None:
    st.set_page_config(page_title="KZ Legislation Analytics", layout="wide")
    st.title("Kazakhstan Legislation Analytics")
    st.caption("KazakhLawCorpus-clean · 215,889 legal acts · 1947–2026")
    if not config.DB_FILE.exists():
        st.error("Database not found. Run `python main.py --all` first.")
        st.stop()
    where, params = build_filters()
    show_kpis(where, params)
    show_trends(where, params)
    show_rankings(where, params)
    show_table(where, params)


main()
