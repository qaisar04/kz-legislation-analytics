"""Split multi-valued fields, classify dimensions and build normalised relational tables.

Contract: build_tables(acts) takes the optimised Parquet DataFrame and returns
{table_name: DataFrame} whose columns match sql/schema.sql one-to-one.
"""
import re

import pandas as pd

from src import config

AREA_SEPARATOR = re.compile(r",\s+(?=[А-ЯӘҒҚҢӨҰҮҺІЁA-Z\"«])")
FORM_SEPARATOR = re.compile(r",\s*")
PARENTHETICAL = re.compile(r"\s*\([^()]*\)")
UNKNOWN = "Белгісіз"
OTHER = "other"

AUTHORITY_RULES = [
    ("judicial", ("Сот", "Конституциялық Кеңес")),
    ("presidential", ("Президент", "Жарлық", "Елбасы", "Мемлекеттік хатшы")),
    ("international", ("Халықаралық", "ТМД")),
    ("local", ("Мәслихат", "Әкім", "Жергілікті", "Тексеру комиссия")),
    ("central_executive", ("Министрлік", "Үкімет", "Премьер", "Орталық атқарушы")),
    ("legislative", ("Заң", "Парламент", "Кеңес", "Кодекс", "Конституц", "Сенат", "Мәжіліс")),
]
BODY_RULES = [
    ("maslikhat", ("мәслихат",)), ("akimat", ("әкімдіг", "әкімдік")), ("akim", ("әкімі",)),
    ("government", ("Үкіметі",)), ("president", ("Президент",)), ("parliament", ("Парламент",)),
    ("court", ("Соты",)), ("national_bank", ("Ұлттық Банк",)),
    ("ministry", ("министрлі",)), ("agency_committee", ("агенттіг", "комитет", "комиссия")),
    ("eurasian", ("Еуразиялық",)), ("local_administration", ("мемлекеттік орган",)),
]
REGION_RULES = [
    ("international", ("ЕурАзЭҚ", "Халықаралық", "ТМД", "Кеден одағы")),
    ("rural_district", ("ауылдық округ", "селолық округ", "кенттік округ", "ауыл", "кенті", "ауылы", "селосы")), ("district", ("ауданы", "аудан")),
    ("oblast", ("облысы",)), ("city", ("қаласы", "қала")), ("national", ("Қазақстан Республикасы",)),
]


def classify(value, rules, case_sensitive=True) -> str:
    """Return the first label whose keywords occur in value (rules are ordered by priority)."""
    if not isinstance(value, str):
        return OTHER
    text = value if case_sensitive else value.lower()
    for label, keywords in rules:
        if any((k if case_sensitive else k.lower()) in text for k in keywords):
            return label
    return OTHER


def strip_parenthetical(name):
    """Parentheticals hold renames/parent units, so they are removed (innermost first) before
    classifying — otherwise "X district (Y oblast)" would match the oblast keyword."""
    if not isinstance(name, str):
        return name
    previous = None
    while previous != name:
        previous, name = name, PARENTHETICAL.sub("", name)
    return name


def classify_region(name) -> str:
    return classify(strip_parenthetical(name), REGION_RULES)


def classify_body(name) -> str:
    return classify(strip_parenthetical(name), BODY_RULES, case_sensitive=False)


def split_multi_value(series: pd.Series, column: str) -> pd.Series:
    pattern = AREA_SEPARATOR if column == config.COL_AREA else FORM_SEPARATOR
    return series.astype("object").map(
        lambda v: [p.strip() for p in pattern.split(v) if p.strip()] if isinstance(v, str) else [])


def build_dimension(values: pd.Series, id_col: str, classifier=None, class_col=None) -> pd.DataFrame:
    names = sorted(values.dropna().astype(str).unique())
    dim = pd.DataFrame({id_col: range(1, len(names) + 1), "name": names})
    if classifier is not None:
        dim["short_name"] = dim["name"].map(strip_parenthetical).str.strip()
        dim[class_col] = dim["name"].map(classifier)
    return dim


def build_bridge(acts: pd.DataFrame, column: str, dim: pd.DataFrame, id_col: str) -> pd.DataFrame:
    exploded = pd.DataFrame({"act_id": acts["act_id"], "name": split_multi_value(acts[column], column)})
    exploded = exploded.explode("name").dropna().drop_duplicates()
    return exploded.merge(dim[[id_col, "name"]], on="name")[["act_id", id_col]]


def map_ids(series: pd.Series, dim: pd.DataFrame, id_col: str) -> pd.Series:
    lookup = dict(zip(dim["name"], dim[id_col]))
    return series.astype("object").map(lookup).astype("Int64")


def iso_date(series: pd.Series) -> pd.Series:
    return series.dt.strftime(config.DATE_FORMAT)


def build_fact_table(acts: pd.DataFrame, dims: dict) -> pd.DataFrame:
    adopted = acts[config.COL_DATE_ADOPTED]
    return pd.DataFrame({
        "act_id": acts["act_id"], "law_id": acts[config.COL_LAW_ID],
        "title": acts[config.COL_TITLE], "description": acts[config.COL_DESCRIPTION],
        "date_adopted": iso_date(adopted), "adoption_year": adopted.dt.year,
        "adoption_month": adopted.dt.month,
        "date_modified": iso_date(acts[config.COL_DATE_MODIFIED]),
        "date_published": iso_date(acts[config.COL_DATE_PUBLISHED]),
        "is_repealed": acts[config.COL_IS_REPEALED].astype(int),
        "adilet_url": acts[config.COL_ADILET_URL],
        "body_id": map_ids(acts[config.COL_ADOPTING_BODY], dims["body"], "body_id"),
        "region_id": map_ids(acts[config.COL_REGION], dims["region"], "region_id"),
        "legal_force_id": map_ids(acts[config.COL_LEGAL_FORCE], dims["legal_force"], "legal_force_id"),
        "section_id": map_ids(acts[config.COL_SECTION], dims["section"], "section_id"),
    })


def build_dimensions(acts: pd.DataFrame) -> dict:
    split_values = {c: split_multi_value(acts[c], c).explode() for c in config.MULTI_VALUE_COLUMNS}
    return {
        "body": build_dimension(acts[config.COL_ADOPTING_BODY], "body_id", classify_body, "body_type"),
        "region": build_dimension(acts[config.COL_REGION], "region_id", classify_region, "region_level"),
        "legal_force": build_dimension(acts[config.COL_LEGAL_FORCE], "legal_force_id",
                                       lambda n: classify(n, AUTHORITY_RULES), "authority_level"),
        "section": build_dimension(acts[config.COL_SECTION], "section_id"),
        "area": build_dimension(split_values[config.COL_AREA], "area_id"),
        "form": build_dimension(split_values[config.COL_ACT_FORM], "form_id"),
    }


def build_tables(acts: pd.DataFrame) -> dict:
    acts = acts.reset_index(drop=True).assign(act_id=lambda d: d.index + 1)
    dims = build_dimensions(acts)
    tables = dict(dims)
    tables["act"] = build_fact_table(acts, dims)
    tables["act_area"] = build_bridge(acts, config.COL_AREA, dims["area"], "area_id")
    tables["act_form"] = build_bridge(acts, config.COL_ACT_FORM, dims["form"], "form_id")
    return tables
