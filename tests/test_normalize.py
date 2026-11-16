import numpy as np
import pandas as pd
import pytest

from src import config, normalize
from src import timeseries as ts

AREA_WITH_INNER_COMMAS = "Нормативтік құқықтық актілер: дайындау, қабылдау, өзгерту"


def test_area_split_keeps_inner_commas():
    value = f"Қаржы, {AREA_WITH_INNER_COMMAS}, Білім"
    result = normalize.split_multi_value(pd.Series([value]), config.COL_AREA)[0]
    assert result == ["Қаржы", AREA_WITH_INNER_COMMAS, "Білім"]


def test_form_split_and_missing():
    result = normalize.split_multi_value(pd.Series(["Шешім, Өзгерту", None]), config.COL_ACT_FORM)
    assert result.tolist() == [["Шешім", "Өзгерту"], []]


@pytest.mark.parametrize("name, level", [
    ("Есіл ауданы (Солтүстік Қазақстан облысы)", "district"),
    ("Түркістан облысы (бұрынғы атауы: Оңтүстік Қазақстан облысы)", "oblast"),
    ("Қызылжар ауылдық округі", "rural_district"),
    ("Қазақстан Республикасы", "national"),
    ("Алматы қаласы", "city"),
])
def test_region_level(name, level):
    assert normalize.classify_region(name) == level


@pytest.mark.parametrize("force, level", [
    ("Конституциялық Соттың қаулысы (бұрынғы атауы: Конституциялық Кеңестің қаулысы)", "judicial"),
    ("Заң күші бар Жарлық", "presidential"),
    ("Мәслихаттың актісі тіркелмеген", "local"),
    ("Үкіметтің қаулысы", "central_executive"),
    ("Заң", "legislative"),
])
def test_authority_level(force, level):
    assert normalize.classify(force, normalize.AUTHORITY_RULES) == level


def test_body_with_nested_parenthetical_is_maslikhat():
    name = "Абай ауданының (Шығыс Қазақстан облысы) мәслихаты (Абай облысына берілді)"
    assert normalize.classify_body(name) == "maslikhat"


def test_forecast_split_has_no_leakage():
    index = pd.date_range("2015-01-01", "2025-12-01", freq="MS")
    monthly = pd.Series(np.arange(len(index)), index=index)
    train, test = ts.split_train_test(monthly)
    assert train.index.max() < test.index.min()
    assert len(test) == 36


def test_seasonal_naive_repeats_last_year():
    index = pd.date_range("2020-01-01", "2022-12-01", freq="MS")
    monthly = pd.Series(range(len(index)), index=index, dtype=float)
    forecast = ts.forecast_seasonal_naive(monthly, 24)
    assert forecast.tolist() == list(range(24, 36)) * 2
