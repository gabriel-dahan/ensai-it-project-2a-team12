"""Tests des objets métier (sans base de données)."""

from datetime import date, timedelta

import pandas as pd
import pytest

from business_object.dju import DjuCalculation, DjuType
from business_object.geo_zone import Department, Municipality, Zoning, haversine_km
from business_object.temperature_report import TemperatureReport
from business_object.user import User

HEATING = DjuType(id=None, name="heating", base_temperature=18, mode="heating")
COOLING = DjuType(id=None, name="cooling", base_temperature=22, mode="cooling")


def report(day, t_min, t_max, observed=True):
    return TemperatureReport(station_id=None, date=day, temp_min=t_min, temp_max=t_max, observed=observed)


def point_data(*days_and_means, not_observed=()):
    """Températures d'un point : (jour, moyenne)... -> (moyennes, observé), indexés par date."""
    days = [day for day, _ in days_and_means]
    means = pd.Series([mean for _, mean in days_and_means], index=days, dtype=float)
    observed = pd.Series([day not in not_observed for day in days], index=days)
    return means, observed


def zone_data(day, means_by_code, not_observed=()):
    """Températures d'un jour pour plusieurs communes : une colonne par code INSEE."""
    means = pd.DataFrame({code: [mean] for code, mean in means_by_code.items()}, index=[day], dtype=float)
    observed = pd.DataFrame({code: [code not in not_observed] for code in means_by_code}, index=[day])
    return means, observed


def calculation(start, end, time_step="day", zone=None):
    return DjuCalculation(id=None, start_date=start, end_date=end, time_step=time_step, type=HEATING, zone=zone)


def days(start, end):
    """Tous les jours de start à end inclus."""
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def municipality(code, population):
    return Municipality(id=None, name=code, insee_code=code, latitude=48.0, longitude=2.0, population=population)


# DjuType

def test_heating_value():
    assert HEATING.compute_daily_value(7) == 11


def test_cooling_value():
    assert COOLING.compute_daily_value(25) == 3


def test_value_is_never_negative():
    assert HEATING.compute_daily_value(25) == 0
    assert COOLING.compute_daily_value(5) == 0


def test_value_on_a_whole_column():
    values = HEATING.compute_daily_value(pd.Series([7.0, 25.0, float("nan")]))
    assert values.iloc[0] == 11 and values.iloc[1] == 0 and pd.isna(values.iloc[2])


# DjuCalculation.run et aggregate

def test_run_by_day():
    calc = calculation(date(2024, 1, 1), date(2024, 1, 2))
    results = calc.run(*point_data((date(2024, 1, 2), 10), (date(2024, 1, 1), 8)))
    assert [r.value for r in results] == [10, 8]
    assert results[0].period_start == results[0].period_end == date(2024, 1, 1)
    assert calc.computed_at == date.today()


def test_run_ignores_missing_values_and_days_outside_period():
    calc = calculation(date(2024, 1, 1), date(2024, 1, 31), "month")
    results = calc.run(*point_data(
        (date(2024, 1, 1), 10),
        (date(2024, 1, 2), float("nan")),
        (date(2024, 2, 1), 0),
    ))
    assert len(results) == 1
    assert results[0].value == 8
    assert results[0].days_with_data == 1


def test_week_is_iso_week_clamped_to_period():
    # 3 janvier 2024 = mercredi ; la semaine suivante commence le lundi 8
    calc = calculation(date(2024, 1, 3), date(2024, 1, 10), "week")
    results = calc.run(*point_data(*[(d, 18) for d in days(date(2024, 1, 3), date(2024, 1, 10))]))
    assert [(r.period_start, r.period_end) for r in results] == [
        (date(2024, 1, 3), date(2024, 1, 7)),
        (date(2024, 1, 8), date(2024, 1, 10)),
    ]
    assert [r.days_with_data for r in results] == [5, 3]


def test_month_uses_calendar_bounds_even_without_data_at_the_edges():
    calc = calculation(date(2024, 1, 15), date(2024, 3, 31), "month")
    results = calc.run(*point_data((date(2024, 2, 10), 8), (date(2024, 1, 20), 8)))
    assert [(r.period_start, r.period_end) for r in results] == [
        (date(2024, 1, 15), date(2024, 1, 31)),
        (date(2024, 2, 1), date(2024, 2, 29)),
    ]


def test_year_aggregation():
    calc = calculation(date(2023, 12, 31), date(2024, 1, 1), "year")
    results = calc.run(*point_data((date(2023, 12, 31), 8), (date(2024, 1, 1), 18)))
    assert [(r.period_start, r.period_end, r.value) for r in results] == [
        (date(2023, 12, 31), date(2023, 12, 31), 10),
        (date(2024, 1, 1), date(2024, 1, 1), 0),
    ]


def test_aggregate_can_change_time_step():
    calc = calculation(date(2024, 1, 1), date(2024, 1, 3))
    calc.run(*point_data(*[(d, 8) for d in days(date(2024, 1, 1), date(2024, 1, 3))]))
    results = calc.aggregate("month")
    assert len(results) == 1 and results[0].value == 30


def test_unknown_time_step():
    calc = calculation(date(2024, 1, 1), date(2024, 1, 3), "hour")
    with pytest.raises(ValueError):
        calc.run(*point_data())


def test_observed_ratio():
    calc = calculation(date(2024, 1, 1), date(2024, 1, 4), "month")
    results = calc.run(*point_data(
        *[(d, 8) for d in days(date(2024, 1, 1), date(2024, 1, 4))], not_observed=[date(2024, 1, 3)]
    ))
    assert results[0].days_with_data == 4
    assert results[0].observed_ratio == 0.75


# DjuCalculation.run_for_zone

def test_run_for_zone_weighted_by_population():
    big, small = municipality("A", 300), municipality("B", 100)
    zone = Department(id=1, name="D", insee_code="01", municipalities=[big, small])
    calc = calculation(date(2024, 1, 1), date(2024, 1, 1), zone=zone)
    # A : 8 DJU, B : 16 DJU (valeur comblée)
    results = calc.run_for_zone(*zone_data(date(2024, 1, 1), {"A": 10, "B": 2}, not_observed=["B"]))
    assert results[0].value == pytest.approx(10)  # (300 * 8 + 100 * 16) / 400
    assert results[0].observed_ratio == 0


def test_run_for_zone_ignores_municipality_without_population():
    zone = Zoning(id=1, name="Z", municipalities=[municipality("A", 100), municipality("B", None)])
    calc = calculation(date(2024, 1, 1), date(2024, 1, 1), zone=zone)
    results = calc.run_for_zone(*zone_data(date(2024, 1, 1), {"A": 10, "B": 2}))
    assert results[0].value == 8


def test_run_for_zone_all_populations_null_gives_simple_mean():
    zone = Zoning(id=1, name="Z", municipalities=[municipality("A", None), municipality("B", 0)])
    calc = calculation(date(2024, 1, 1), date(2024, 1, 1), zone=zone)
    results = calc.run_for_zone(*zone_data(date(2024, 1, 1), {"A": 10, "B": 2}))
    assert results[0].value == 12


def test_run_for_zone_uses_only_municipalities_with_data_that_day():
    zone = Zoning(id=1, name="Z", municipalities=[municipality("A", 100), municipality("B", 100)])
    calc = calculation(date(2024, 1, 1), date(2024, 1, 1), zone=zone)
    results = calc.run_for_zone(*zone_data(date(2024, 1, 1), {"A": 10, "B": float("nan")}, not_observed=["B"]))
    assert results[0].value == 8
    assert results[0].observed_ratio == 1  # B n'a pas de valeur, elle ne compte pas


def test_run_for_zone_uses_only_columns_of_its_municipalities():
    zone = Zoning(id=1, name="Z", municipalities=[municipality("A", 100)])
    calc = calculation(date(2024, 1, 1), date(2024, 1, 1), zone=zone)
    results = calc.run_for_zone(*zone_data(date(2024, 1, 1), {"A": 10, "OTHER": -20}))
    assert results[0].value == 8


# Géographie et relevés

def test_haversine_paris_lyon():
    assert haversine_km(48.8566, 2.3522, 45.7640, 4.8357) == pytest.approx(392, abs=2)


def test_daily_mean():
    assert report(date(2024, 1, 1), 4, 10).daily_mean() == 7
    assert report(date(2024, 1, 1), None, 10).daily_mean() is None


def test_altitude_correction():
    corrected = report(date(2024, 1, 1), 10, None).apply_altitude_correction(100)
    assert corrected.temp_min == pytest.approx(9.35)  # -0,65 °C pour 100 m de plus
    assert corrected.temp_max is None


def test_zoning_add_remove_by_insee_code():
    zoning = Zoning(id=None, name="Z")
    zoning.add_municipality(municipality("A", 1))
    zoning.add_municipality(municipality("A", 1))
    zoning.add_municipality(municipality("B", 1))
    assert [m.insee_code for m in zoning.get_municipalities()] == ["A", "B"]
    zoning.remove_municipality(municipality("A", 1))
    assert [m.insee_code for m in zoning.get_municipalities()] == ["B"]


def test_zoning_is_owned_by():
    zoning = Zoning(id=None, name="Z", owner_id=1)
    assert zoning.is_owned_by(User.from_storage(1, "alice", "hash"))
    assert not zoning.is_owned_by(User.from_storage(2, "bob", "hash"))
    assert not zoning.is_owned_by(None)


def test_zone_type():
    assert Zoning(id=None, name="Z").zone_type == "zoning"
    assert municipality("A", 1).zone_type == "municipality"


# Utilisateur

def test_check_password():
    user = User(username="alice", password="secret")
    assert user.check_password("secret")
    assert not user.check_password("wrong")
    reloaded = User.from_storage(1, "alice", user.password_hash)
    assert reloaded.check_password("secret")


def test_create_zoning():
    user = User(username="alice", password="secret", id=5)
    zoning = user.create_zoning("Mon zonage", "Description")
    assert (zoning.name, zoning.description, zoning.owner_id) == ("Mon zonage", "Description", 5)
    assert zoning.is_owned_by(user)
