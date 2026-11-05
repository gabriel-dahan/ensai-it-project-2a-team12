"""Tests de la couche service, sans base de données : les DAO sont remplacées par de faux objets."""

from datetime import UTC, date, datetime, timedelta

import jwt
import pandas as pd
import pytest

from business_object.dju import DjuResult
from business_object.geo_zone import Department, Municipality, Region, Zoning
from business_object.meteo_station import MeteoStation
from business_object.user import User
from schema.dju_schema import DjuPointRequest, DjuZoneRequest
from service.auth_service import AuthService
from service.dju_service import DjuService
from service.errors import ServiceError
from service.temperature_service import TemperatureService
from service.zone_service import ZoneService

DAY1 = date(2024, 1, 1)
DAY2 = date(2024, 1, 2)
FIRST_DATA_DAY = date(1990, 1, 1)  # période des relevés renvoyée par FakeTemperatureService
LAST_DATA_DAY = date(2024, 12, 31)


# ---------- Faux objets ----------


class FakeStationDao:
    def __init__(self, stations):
        self.stations = stations

    def get_all_stations(self):
        return list(self.stations)


class FakeReportDao:
    """Relevés : {station_id: [(jour, température moyenne, observé), ...]}."""

    def __init__(self, reports_by_station):
        self.reports_by_station = reports_by_station
        self.requested = []  # stations demandées, appel par appel

    def get_reports_dataframe(self, station_ids, start_date, end_date):
        self.requested.append(list(station_ids))
        return reports_table({i: self.reports_by_station.get(i, []) for i in station_ids})


class FakeTemperatureService:
    """Renvoie les mêmes températures moyennes ({jour: moyenne}) pour tous les lieux."""

    def __init__(self, stations, daily_means):
        self.stations = stations
        self.daily_means = daily_means
        self.estimate_calls = 0
        self.municipality_calls = 0

    def get_data_period(self):
        return FIRST_DATA_DAY, LAST_DATA_DAY

    def find_candidate_stations(self, locations, *args):
        return {key: self.stations for key in locations}, None

    def estimate_daily_temperatures(self, locations, stations, reports):
        self.estimate_calls += 1
        return self._tables(list(locations))

    def get_municipality_temperatures(self, municipalities, *args):
        self.municipality_calls += 1
        return self._tables([m.insee_code for m in municipalities])

    def _tables(self, keys):
        days = sorted(self.daily_means)
        means = pd.DataFrame(
            {key: [self.daily_means[d] for d in days] for key in keys}, index=days, dtype=float
        )
        observed = pd.DataFrame({key: [True] * len(days) for key in keys}, index=days)
        return means, observed


class FakeDjuDao:
    def __init__(self, stored_id=None, stored_results=None):
        self.stored_id = stored_id
        self.stored_results = stored_results or []
        self.saved = []
        self.deleted = []

    def get_or_create_dju_type(self, mode, threshold):
        return 7

    def find_calculation(self, *args):
        return self.stored_id

    def get_calculation_results(self, calculation_id):
        return self.stored_results

    def save_calculation(self, calculation):
        self.saved.append(calculation)
        return 99

    def delete_calculations_for_zone(self, zone_type, zone_id):
        self.deleted.append((zone_type, zone_id))
        return 1


class FakeGeoZoneDao:
    def __init__(self, municipalities, department=None, region=None):
        self.municipalities = municipalities
        self.department = department
        self.region = region

    def get_department_by_id(self, department_id, with_municipalities=False):
        return self.department

    def get_region_by_id(self, region_id, with_municipalities=False):
        return self.region

    def get_municipalities_by_insee(self, codes):
        return [m for m in self.municipalities if m.insee_code in codes]


class FakeZoningDao:
    def __init__(self, zoning=None):
        self.zoning = zoning
        self.created = None
        self.updated = None
        self.deleted = None

    def create(self, zoning):
        zoning.id = 1
        self.created = zoning
        return zoning

    def find_by_id(self, zoning_id):
        return self.zoning

    def update(self, zoning):
        self.updated = zoning

    def delete(self, zoning_id):
        self.deleted = zoning_id
        return True


class FakeUserDao:
    def __init__(self, users=None):
        self.users = users or []

    def find_by_username(self, username):
        return next((u for u in self.users if u.username == username), None)

    def find_by_id(self, user_id):
        return next((u for u in self.users if u.id == user_id), None)

    def create(self, user):
        user.id = len(self.users) + 1
        self.users.append(user)
        return user


def municipality(insee_code, population=100):
    return Municipality(
        id=int(insee_code),
        name=f"Commune {insee_code}",
        insee_code=insee_code,
        latitude=48.0,
        longitude=-1.6,
        altitude=50.0,
        population=population,
    )


def reports_table(reports_by_station):
    """Relevés au format de TemperatureReportDao.get_reports_dataframe."""
    rows = [
        (station_id, day, mean, observed)
        for station_id, reports in reports_by_station.items()
        for day, mean, observed in reports
    ]
    return pd.DataFrame(rows, columns=["station_id", "date", "temp_mean", "observed"])


def make_zone_service(municipalities=(), department=None, region=None, zoning=None, dju_dao=None):
    return ZoneService(
        zone_dao=FakeGeoZoneDao(list(municipalities), department=department, region=region),
        zoning_dao=FakeZoningDao(zoning),
        dju_dao=dju_dao or FakeDjuDao(),
    )


ALICE = User.from_storage(user_id=1, username="alice", password_hash="x")
BOB = User.from_storage(user_id=2, username="bob", password_hash="x")


# ---------- TemperatureService ----------

# Sur l'équateur, A est à 0,1° et B à 0,2° du point (0, 0) : poids 1/d² dans le rapport 4 pour 1
STATION_A = MeteoStation(id=1, station_code="A", name="A", latitude=0.0, longitude=0.1)
STATION_B = MeteoStation(id=2, station_code="B", name="B", latitude=0.0, longitude=-0.2)
ORIGIN = {"lieu": (0.0, 0.0, None)}


def test_idw_two_stations():
    reports = reports_table({1: [(DAY1, 15.0, True)], 2: [(DAY1, 7.5, False)]})
    service = TemperatureService(FakeStationDao([]), FakeReportDao({}))

    means, observed = service.estimate_daily_temperatures(
        ORIGIN, {"lieu": [STATION_A, STATION_B]}, reports
    )

    assert means.loc[DAY1, "lieu"] == pytest.approx((4 * 15.0 + 7.5) / 5)  # 13.5
    assert not observed.loc[DAY1, "lieu"]  # B est une valeur comblée


def test_idw_uses_only_stations_with_a_value():
    reports = reports_table({1: [(DAY2, 10.0, True)], 2: [(DAY1, 6.0, True), (DAY2, 5.0, True)]})
    service = TemperatureService(FakeStationDao([]), FakeReportDao({}))

    means, observed = service.estimate_daily_temperatures(
        ORIGIN, {"lieu": [STATION_A, STATION_B]}, reports
    )

    assert means.loc[DAY1, "lieu"] == pytest.approx(6.0)  # A n'a pas de valeur le 1er
    assert means.loc[DAY2, "lieu"] == pytest.approx((4 * 10.0 + 5.0) / 5)
    assert observed.loc[DAY1, "lieu"]


def test_altitude_correction():
    station = MeteoStation(id=1, station_code="A", name="A", latitude=0.0, longitude=0.1, altitude=100.0)
    service = TemperatureService(FakeStationDao([]), FakeReportDao({}))

    means, _ = service.estimate_daily_temperatures(
        {"lieu": (0.0, 0.0, 300.0)}, {"lieu": [station]}, reports_table({1: [(DAY1, 15.0, True)]})
    )

    # 200 m plus haut : -0,0065 x 200 = -1,3 °C
    assert means.loc[DAY1, "lieu"] == pytest.approx(13.7)


def test_location_without_station_gives_empty_column():
    service = TemperatureService(FakeStationDao([]), FakeReportDao({}))

    means, _ = service.estimate_daily_temperatures(
        {"A": (0.0, 0.0, None), "B": (0.0, 0.0, None)},
        {"A": [STATION_A], "B": []},
        reports_table({1: [(DAY1, 15.0, True)]}),
    )

    assert list(means.columns) == ["A", "B"]
    assert means["B"].isna().all()


def test_candidate_stations_skip_stations_without_reports():
    stations = [
        MeteoStation(id=i, station_code=str(i), name=None, latitude=0.0, longitude=0.1 * i)
        for i in range(1, 6)
    ]
    report_dao = FakeReportDao({3: [(DAY1, 1.0, True)], 5: [(DAY1, 2.0, True)]})
    service = TemperatureService(FakeStationDao(stations), report_dao)

    chosen, reports = service.find_candidate_stations(ORIGIN, 2, DAY1, DAY1)

    # 1 et 2 n'ont rien : remplacées par 3 et 4 ; 4 n'a rien non plus : remplacée par 5
    assert [s.id for s in chosen["lieu"]] == [3, 5]
    assert report_dao.requested == [[1, 2], [3, 4], [5]]
    assert sorted(reports["station_id"]) == [3, 5]


def test_station_shared_by_two_locations_is_read_once():
    report_dao = FakeReportDao({1: [(DAY1, 1.0, True)], 2: [(DAY1, 2.0, True)]})
    service = TemperatureService(FakeStationDao([STATION_A, STATION_B]), report_dao)
    locations = {"X": (0.0, 0.05, None), "Y": (0.0, -0.05, None)}

    chosen, _ = service.find_candidate_stations(locations, 2, DAY1, DAY1)

    assert {s.id for s in chosen["X"]} == {s.id for s in chosen["Y"]} == {1, 2}
    assert report_dao.requested == [[1, 2]]  # une seule requête pour les deux lieux


def test_municipality_temperatures_one_column_per_municipality():
    station = MeteoStation(id=1, station_code="A", name="A", latitude=48.0, longitude=-1.5, altitude=0.0)
    service = TemperatureService(FakeStationDao([station]), FakeReportDao({1: [(DAY1, 10.0, True)]}))

    means, _ = service.get_municipality_temperatures(
        [municipality("35238"), municipality("35047")], DAY1, DAY1, use_altitude=False
    )

    assert list(means.columns) == ["35238", "35047"]
    assert means.loc[DAY1, "35238"] == pytest.approx(10.0)  # sans correction d'altitude


# ---------- DjuService : point ----------


def point_request(**kwargs):
    values = {"latitude": 48.0, "longitude": -1.6, "start_date": DAY1, "end_date": DAY2}
    values.update(kwargs)
    return DjuPointRequest(**values)


def test_point_without_threshold_is_400():
    service = DjuService(FakeTemperatureService([], {}), make_zone_service(), FakeDjuDao())
    with pytest.raises(ServiceError) as error:
        service.calculate_point_dju(point_request())
    assert error.value.status_code == 400


def test_point_with_dates_in_wrong_order_is_400():
    service = DjuService(FakeTemperatureService([], {}), make_zone_service(), FakeDjuDao())
    with pytest.raises(ServiceError) as error:
        service.calculate_point_dju(point_request(start_date=DAY2, end_date=DAY1, heating_threshold=18))
    assert error.value.status_code == 400


def test_point_without_station_is_404():
    service = DjuService(FakeTemperatureService([], {}), make_zone_service(), FakeDjuDao())
    with pytest.raises(ServiceError) as error:
        service.calculate_point_dju(point_request(heating_threshold=18))
    assert error.value.status_code == 404


def test_point_with_two_thresholds():
    station = MeteoStation(id=1, station_code="A", name="A", latitude=48.0, longitude=-1.5)
    temperatures = FakeTemperatureService([station], {DAY1: 5.0, DAY2: 5.0})
    service = DjuService(temperatures, make_zone_service(), FakeDjuDao())

    result = service.calculate_point_dju(
        point_request(heating_threshold=18, cooling_threshold=2, time_step="day")
    )

    assert set(result) == {"heating", "cooling"}
    assert [r.value for r in result["heating"].results] == [pytest.approx(13.0)] * 2
    assert [r.value for r in result["cooling"].results] == [pytest.approx(3.0)] * 2
    assert temperatures.estimate_calls == 1  # températures estimées une seule fois


def test_point_period_cut_to_available_data():
    station = MeteoStation(id=1, station_code="A", name="A", latitude=48.0, longitude=-1.5)
    service = DjuService(FakeTemperatureService([station], {}), make_zone_service(), FakeDjuDao())

    result = service.calculate_point_dju(
        point_request(start_date=date(1985, 6, 1), end_date=date(2030, 1, 1), heating_threshold=18)
    )

    assert result["heating"].start_date == FIRST_DATA_DAY
    assert result["heating"].end_date == LAST_DATA_DAY


def test_point_period_without_data_is_400():
    service = DjuService(FakeTemperatureService([], {}), make_zone_service(), FakeDjuDao())
    with pytest.raises(ServiceError) as error:
        service.calculate_point_dju(
            point_request(start_date=date(2030, 1, 1), end_date=date(2030, 12, 31), heating_threshold=18)
        )
    assert error.value.status_code == 400


# ---------- DjuService : zone ----------


def zone_request(**kwargs):
    values = {
        "zone_type": "department",
        "zone_id": 35,
        "start_date": DAY1,
        "end_date": DAY1,
        "heating_threshold": 18,
        "cooling_threshold": 2,
    }
    values.update(kwargs)
    return DjuZoneRequest(**values)


def make_department():
    department = Department(id=35, name="Ille-et-Vilaine", insee_code="35")
    department.add_municipality(municipality("35238"))
    department.add_municipality(municipality("35047"))
    return department


def test_zone_not_in_cache_is_computed_and_saved():
    temperatures = FakeTemperatureService([], {DAY1: 5.0})
    dju_dao = FakeDjuDao(stored_id=None)
    service = DjuService(temperatures, make_zone_service(department=make_department()), dju_dao)

    result = service.calculate_zone_dju(zone_request(), None)

    assert len(result) == 2  # une sous-zone, deux modes
    assert result[0].results[0].value == pytest.approx(13.0)
    assert len(dju_dao.saved) == 2
    assert temperatures.municipality_calls == 1  # une fois pour toutes les communes et les deux modes


def test_zone_found_in_cache():
    stored = [DjuResult(id=1, period_start=DAY1, period_end=DAY1, value=42.0, days_with_data=1, observed_ratio=1.0)]
    temperatures = FakeTemperatureService([], {})
    dju_dao = FakeDjuDao(stored_id=5, stored_results=stored)
    service = DjuService(temperatures, make_zone_service(department=make_department()), dju_dao)

    result = service.calculate_zone_dju(zone_request(cooling_threshold=None), None)

    assert len(result) == 1
    assert result[0].id == 5
    assert result[0].results[0].value == 42.0
    assert temperatures.municipality_calls == 0
    assert dju_dao.saved == []


def test_zone_by_municipality():
    temperatures = FakeTemperatureService([], {DAY1: 5.0})
    service = DjuService(temperatures, make_zone_service(department=make_department()), FakeDjuDao())

    result = service.calculate_zone_dju(
        zone_request(cooling_threshold=None, aggregation_level="municipality"), None
    )

    assert [c.zone.insee_code for c in result] == ["35238", "35047"]
    assert temperatures.municipality_calls == 1  # une seule estimation pour les deux sous-zones


def test_zone_period_cut_before_cache_lookup():
    temperatures = FakeTemperatureService([], {DAY1: 5.0})
    service = DjuService(temperatures, make_zone_service(department=make_department()), FakeDjuDao())

    result = service.calculate_zone_dju(
        zone_request(cooling_threshold=None, end_date=date(2030, 1, 1)), None
    )

    # Le calcul (et donc sa clé de cache) porte sur la période réellement couverte
    assert result[0].end_date == LAST_DATA_DAY


# ---------- ZoneService ----------


def make_zoning(owner_id=1):
    zoning = Zoning(id=5, name="Mon zonage", owner_id=owner_id)
    zoning.add_municipality(municipality("35238"))
    return zoning


def test_get_zoning_without_user_is_401():
    with pytest.raises(ServiceError) as error:
        make_zone_service(zoning=make_zoning()).get_zone("zoning", 5, None)
    assert error.value.status_code == 401


def test_get_zoning_of_another_user_is_403():
    with pytest.raises(ServiceError) as error:
        make_zone_service(zoning=make_zoning(owner_id=1)).get_zone("zoning", 5, BOB)
    assert error.value.status_code == 403


def test_get_missing_zoning_is_404():
    with pytest.raises(ServiceError) as error:
        make_zone_service(zoning=None).get_zone("zoning", 5, ALICE)
    assert error.value.status_code == 404


def test_get_missing_department_is_404():
    with pytest.raises(ServiceError) as error:
        make_zone_service(department=None).get_zone("department", 99)
    assert error.value.status_code == 404


def test_sub_zones_of_region_by_department():
    region = Region(id=53, name="Bretagne", insee_code="53")
    region.add_department(make_department())
    service = make_zone_service()
    assert [d.insee_code for d in service.get_sub_zones(region, "department")] == ["35"]
    with pytest.raises(ServiceError):
        service.get_sub_zones(make_zoning(), "department")


def test_create_zoning_with_unknown_code_is_400():
    service = make_zone_service(municipalities=[municipality("35238")])
    with pytest.raises(ServiceError) as error:
        service.create_zoning(ALICE, "Test", None, ["35238", "99999"])
    assert error.value.status_code == 400
    assert "99999" in str(error.value)


def test_import_csv_with_header():
    service = make_zone_service(municipalities=[municipality("35238"), municipality("35047")])
    content = "nom;code_insee\nRennes;35238\nBetton;35047\nRennes;35238\n"

    zoning = service.import_zoning(ALICE, "rennes.csv", content)

    assert zoning.name == "rennes"
    assert zoning.owner_id == ALICE.id
    assert [m.insee_code for m in zoning.municipalities] == ["35238", "35047"]


def test_import_csv_first_column():
    service = make_zone_service(municipalities=[municipality("35238"), municipality("35047")])
    zoning = service.import_zoning(ALICE, "z.csv", "35238,Rennes\n35047,Betton\n", name="Mon nom")
    assert zoning.name == "Mon nom"
    assert len(zoning.municipalities) == 2


def test_import_json_list_and_object():
    service = make_zone_service(municipalities=[municipality("35238"), municipality("35047")])
    from_list = service.import_zoning(ALICE, "a.json", '["35238", "35047"]')
    from_object = service.import_zoning(ALICE, "b.json", '{"codes_insee": ["35047"]}')
    assert len(from_list.municipalities) == 2
    assert [m.insee_code for m in from_object.municipalities] == ["35047"]


@pytest.mark.parametrize(
    ("filename", "content"),
    [("z.txt", "35238"), ("z.json", "pas du json"), ("z.json", '{"autre": 1}'), ("z.csv", "")],
)
def test_import_bad_file_is_400(filename, content):
    service = make_zone_service(municipalities=[municipality("35238")])
    with pytest.raises(ServiceError) as error:
        service.import_zoning(ALICE, filename, content)
    assert error.value.status_code == 400


def test_update_zoning_deletes_stored_calculations():
    dju_dao = FakeDjuDao()
    zoning = make_zoning()
    service = make_zone_service(
        municipalities=[municipality("35047")], zoning=zoning, dju_dao=dju_dao
    )

    updated = service.update_zoning(ALICE, 5, "Nouvelle description", ["35047"], ["35238"])

    assert [m.insee_code for m in updated.municipalities] == ["35047"]
    assert updated.description == "Nouvelle description"
    assert service.zoning_dao.updated is zoning
    assert dju_dao.deleted == [("zoning", 5)]


def test_update_zoning_of_another_user_is_403():
    dju_dao = FakeDjuDao()
    service = make_zone_service(zoning=make_zoning(owner_id=1), dju_dao=dju_dao)
    with pytest.raises(ServiceError) as error:
        service.update_zoning(BOB, 5, None, [], [])
    assert error.value.status_code == 403
    assert dju_dao.deleted == []


def test_delete_zoning():
    dju_dao = FakeDjuDao()
    service = make_zone_service(zoning=make_zoning(), dju_dao=dju_dao)
    service.delete_zoning(ALICE, 5)
    assert dju_dao.deleted == [("zoning", 5)]
    assert service.zoning_dao.deleted == 5


# ---------- AuthService ----------


@pytest.fixture
def jwt_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "secret-de-test-assez-long-pour-hs256")
    return "secret-de-test-assez-long-pour-hs256"


def test_register_existing_username_is_409():
    service = AuthService(FakeUserDao([ALICE]))
    with pytest.raises(ServiceError) as error:
        service.register("alice", "motdepasse")
    assert error.value.status_code == 409


def test_register_creates_user():
    service = AuthService(FakeUserDao())
    user = service.register("carol", "motdepasse")
    assert user.id == 1
    assert user.check_password("motdepasse")


def test_login_with_wrong_password_is_401(jwt_secret):
    service = AuthService(FakeUserDao([User(username="dave", password="bon", id=4)]))
    with pytest.raises(ServiceError) as error:
        service.authenticate("dave", "mauvais")
    assert error.value.status_code == 401


def test_valid_token_gives_user(jwt_secret):
    dave = User(username="dave", password="bon", id=4)
    service = AuthService(FakeUserDao([dave]))
    token = service.authenticate("dave", "bon")
    assert jwt.decode(token, jwt_secret, algorithms=["HS256"])["sub"] == "4"
    assert service.get_current_user(token) is dave


def test_invalid_token_is_401(jwt_secret):
    service = AuthService(FakeUserDao([ALICE]))
    wrong_key = jwt.encode({"sub": "1"}, "autre-cle-de-test-assez-longue-pour-hs256", algorithm="HS256")
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.now(UTC) - timedelta(hours=1)}, jwt_secret, algorithm="HS256"
    )
    for token in ("n-importe-quoi", wrong_key, expired):
        with pytest.raises(ServiceError) as error:
            service.get_current_user(token)
        assert error.value.status_code == 401
