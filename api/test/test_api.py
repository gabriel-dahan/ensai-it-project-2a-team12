"""Tests de la couche API, sans base : les services sont remplacés par de faux objets."""

import inspect
from datetime import date

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import main
from business_object.dju import DjuCalculation, DjuResult, DjuType
from business_object.geo_zone import Department, Municipality, Region, Zoning
from business_object.user import User
from controllers import dju_controller, user_controller, zone_controller
from controllers.dependencies import get_current_user
from service.errors import ServiceError

ALICE = User.from_storage(user_id=1, username="alice", password_hash="hash")

POINT_BODY = {
    "latitude": 48.1,
    "longitude": -1.7,
    "start_date": "2024-01-01",
    "end_date": "2024-01-02",
    "heating_threshold": 18,
    "cooling_threshold": 22,
}

ZONE_BODY = {
    "zone_type": "region",
    "zone_id": 1,
    "aggregation_level": "department",
    "start_date": "2024-01-01",
    "end_date": "2024-01-01",
    "heating_threshold": 18,
    "cooling_threshold": 22,
}


def make_calculation(mode, zone=None, value=5.0):
    """Construit un calcul avec un seul résultat."""
    return DjuCalculation(
        id=None,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 1),
        time_step="day",
        type=DjuType(id=None, name=mode, base_temperature=18.0, mode=mode),
        zone=zone,
        results=[
            DjuResult(
                id=None,
                period_start=date(2024, 1, 1),
                period_end=date(2024, 1, 1),
                value=value,
                days_with_data=1,
                observed_ratio=1.0,
            )
        ],
    )


def make_municipality(code, name):
    return Municipality(id=None, name=name, insee_code=code, latitude=48.0, longitude=-1.0)


def make_zoning(name="Mon zonage", codes=("35238",)):
    zoning = Zoning(id=7, name=name, description="test", owner_id=ALICE.id)
    for code in codes:
        zoning.add_municipality(make_municipality(code, "Commune " + code))
    return zoning


class FakeDjuService:
    def __init__(self):
        self.calls = []

    def calculate_point_dju(self, request):
        self.calls.append(request)
        return {"heating": make_calculation("heating", value=10.0),
                "cooling": make_calculation("cooling", value=0.0)}

    def calculate_zone_dju(self, request, user):
        self.calls.append((request, user))
        d35 = Department(id=35, name="Ille-et-Vilaine", insee_code="35")
        d29 = Department(id=29, name="Finistère", insee_code="29")
        return [
            make_calculation("heating", d35, 8.0),
            make_calculation("cooling", d35, 0.0),
            make_calculation("heating", d29, 7.0),
            make_calculation("cooling", d29, 0.0),
        ]


class FakeZoneService:
    def __init__(self):
        self.calls = []

    def list_public_zones(self, zone_type):
        self.calls.append(("list", zone_type))
        return [Region(id=1, name="Bretagne", insee_code="53"),
                Department(id=35, name="Ille-et-Vilaine", insee_code="35", region_id=1)]

    def get_zone(self, zone_type, zone_id, user=None):
        if zone_id == 999:
            raise ServiceError("Zone introuvable", status_code=404)
        dep = Department(id=zone_id, name="Ille-et-Vilaine", insee_code="35")
        dep.add_municipality(make_municipality("35238", "Rennes"))
        return dep

    def list_user_zonings(self, user):
        return [make_zoning()]

    def create_zoning(self, user, name, description, codes_insee):
        self.calls.append(("create", user, name, description, codes_insee))
        return make_zoning(name, codes_insee)

    def import_zoning(self, user, filename, content, description=None, name=None):
        self.calls.append(("import", user, filename, content, description, name))
        return make_zoning(name or "import", ["35238", "29019"])

    def update_zoning(self, user, zoning_id, description, add_codes_insee, remove_codes_insee):
        self.calls.append(("update", zoning_id, description, add_codes_insee, remove_codes_insee))
        if zoning_id == 8:
            raise ServiceError("Accès interdit", status_code=403)
        return make_zoning(codes=add_codes_insee)

    def delete_zoning(self, user, zoning_id):
        self.calls.append(("delete", zoning_id))


class FakeAuthService:
    def register(self, username, password):
        if username == "pris":
            raise ServiceError("Nom déjà utilisé", status_code=409)
        return User.from_storage(user_id=2, username=username, password_hash="hash")

    def authenticate(self, username, password):
        if password != "bonmotdepasse":
            raise ServiceError("Identifiants invalides", status_code=401)
        return "jeton"


@pytest.fixture
def client():
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


@pytest.fixture
def dju_service(monkeypatch):
    fake = FakeDjuService()
    monkeypatch.setattr(dju_controller, "service", fake)
    return fake


@pytest.fixture
def zone_service(monkeypatch):
    fake = FakeZoneService()
    monkeypatch.setattr(zone_controller, "service", fake)
    return fake


@pytest.fixture
def logged_in():
    main.app.dependency_overrides[get_current_user] = lambda: ALICE


# Général


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_routes_are_not_async():
    routers = [main.app.router, dju_controller.router, zone_controller.router,
               zone_controller.user_router, user_controller.router]
    routes = [r for router in routers for r in router.routes if isinstance(r, APIRoute)]
    assert len(routes) == 14
    for route in routes:
        assert not inspect.iscoroutinefunction(route.endpoint), route.path


def test_root_redirects_to_docs(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"].endswith("/docs")


# DJU


def test_unknown_zone_type_is_422(client, dju_service):
    response = client.post("/dju/zone", json={**ZONE_BODY, "zone_type": "commune"})
    assert response.status_code == 422


def test_invalid_time_step_is_422(client, dju_service):
    response = client.post("/dju/point", json={**POINT_BODY, "time_step": "hour"})
    assert response.status_code == 422


def test_week_time_step_is_accepted(client, dju_service):
    response = client.post("/dju/point", json={**POINT_BODY, "time_step": "week"})
    assert response.status_code == 200
    assert dju_service.calls[0].time_step == "week"


def test_point_json(client, dju_service):
    response = client.post("/dju/point", json=POINT_BODY)
    assert response.status_code == 200
    body = response.json()
    assert set(body["results"]) == {"heating", "cooling"}
    assert body["results"]["heating"] == [{
        "period_start": "2024-01-01",
        "period_end": "2024-01-01",
        "value": 10.0,
        "days_with_data": 1,
        "observed_ratio": 1.0,
    }]


def test_point_csv(client, dju_service):
    response = client.post("/dju/point?format=csv", json=POINT_BODY)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    lines = response.text.strip().splitlines()
    assert lines[0] == "zone,mode,period_start,period_end,value,days_with_data,observed_ratio"
    assert lines[1] == "point,heating,2024-01-01,2024-01-01,10.0,1,1.0"
    assert len(lines) == 3


def test_unknown_format_is_422(client, dju_service):
    response = client.post("/dju/point?format=xml", json=POINT_BODY)
    assert response.status_code == 422


def test_zone_json_several_sub_zones(client, dju_service):
    response = client.post("/dju/zone", json=ZONE_BODY)
    assert response.status_code == 200
    zones = response.json()["zones"]
    assert [z["name"] for z in zones] == ["Ille-et-Vilaine", "Finistère"]
    assert zones[0]["zone_type"] == "department"
    assert zones[0]["zone_id"] == 35
    assert set(zones[0]["results"]) == {"heating", "cooling"}
    assert zones[1]["results"]["heating"][0]["value"] == 7.0
    request, user = dju_service.calls[0]
    assert request.aggregation_level == "department"
    assert request.use_altitude is True
    assert user is None


def test_zone_csv(client, dju_service):
    response = client.post("/dju/zone?format=csv", json=ZONE_BODY)
    lines = response.text.strip().splitlines()
    assert len(lines) == 5
    assert lines[3].startswith("Finistère,heating,")


def test_service_error_becomes_http_error(client, monkeypatch):
    class FailingDjuService:
        def calculate_point_dju(self, request):
            raise ServiceError("Aucune station disponible", status_code=404)

    monkeypatch.setattr(dju_controller, "service", FailingDjuService())
    response = client.post("/dju/point", json=POINT_BODY)
    assert response.status_code == 404
    assert response.json()["detail"] == "Aucune station disponible"


# Zones officielles


def test_list_zones(client, zone_service):
    response = client.get("/zones?type=all")
    assert response.status_code == 200
    assert response.json() == [
        {"id": 1, "name": "Bretagne", "zone_type": "region", "insee_code": "53"},
        {"id": 35, "name": "Ille-et-Vilaine", "zone_type": "department", "insee_code": "35"},
    ]
    assert zone_service.calls == [("list", "all")]


def test_list_zones_unknown_type_is_422(client, zone_service):
    assert client.get("/zones?type=planete").status_code == 422


def test_zone_detail(client, zone_service):
    response = client.get("/zones/department/35")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Ille-et-Vilaine"
    assert body["municipalities"] == [{"insee_code": "35238", "name": "Rennes"}]


def test_zone_detail_not_found(client, zone_service):
    assert client.get("/zones/department/999").status_code == 404


def test_zone_detail_rejects_zoning(client, zone_service):
    assert client.get("/zones/zoning/7").status_code == 422


# Zonages personnels


def test_zonings_require_token(client, zone_service):
    assert client.get("/user/zones").status_code == 401
    assert client.post("/user/zones", json={"name": "a", "codes_insee": ["35238"]}).status_code == 401


def test_list_my_zonings(client, zone_service, logged_in):
    response = client.get("/user/zones")
    assert response.status_code == 200
    assert response.json()[0]["codes_insee"] == ["35238"]


def test_create_zoning(client, zone_service, logged_in):
    body = {"name": "Rennes et Brest", "description": "test", "codes_insee": ["35238", "29019"]}
    response = client.post("/user/zones", json=body)
    assert response.status_code == 201
    assert response.json()["name"] == "Rennes et Brest"
    assert response.json()["codes_insee"] == ["35238", "29019"]
    assert zone_service.calls[0] == ("create", ALICE, "Rennes et Brest", "test", ["35238", "29019"])


def test_create_zoning_without_name_is_422(client, zone_service, logged_in):
    assert client.post("/user/zones", json={"codes_insee": ["35238"]}).status_code == 422


def test_import_zoning(client, zone_service, logged_in):
    body = {"filename": "zonage.csv", "content": "code_insee\n35238\n29019\n"}
    response = client.post("/user/zones/import", json=body)
    assert response.status_code == 201
    assert response.json()["codes_insee"] == ["35238", "29019"]
    assert zone_service.calls[0] == ("import", ALICE, "zonage.csv", body["content"], None, None)


def test_update_zoning(client, zone_service, logged_in):
    response = client.patch("/user/zones/7", json={"add_codes_insee": ["29019"]})
    assert response.status_code == 200
    assert response.json()["codes_insee"] == ["29019"]
    assert zone_service.calls[0] == ("update", 7, None, ["29019"], [])


def test_update_zoning_forbidden(client, zone_service, logged_in):
    response = client.patch("/user/zones/8", json={"description": "x"})
    assert response.status_code == 403


def test_delete_zoning(client, zone_service, logged_in):
    response = client.delete("/user/zones/7")
    assert response.status_code == 204
    assert zone_service.calls == [("delete", 7)]


# Utilisateurs


def test_register(client, monkeypatch):
    monkeypatch.setattr(user_controller, "service", FakeAuthService())
    response = client.post("/user/register", json={"username": "bob", "password": "motdepasse"})
    assert response.status_code == 201
    assert response.json() == {"id": 2, "username": "bob"}


def test_register_name_taken(client, monkeypatch):
    monkeypatch.setattr(user_controller, "service", FakeAuthService())
    response = client.post("/user/register", json={"username": "pris", "password": "motdepasse"})
    assert response.status_code == 409


def test_login(client, monkeypatch):
    monkeypatch.setattr(user_controller, "service", FakeAuthService())
    response = client.post("/user/login", json={"username": "bob", "password": "bonmotdepasse"})
    assert response.status_code == 200
    assert response.json() == {"access_token": "jeton", "token_type": "bearer"}


def test_login_wrong_password(client, monkeypatch):
    monkeypatch.setattr(user_controller, "service", FakeAuthService())
    response = client.post("/user/login", json={"username": "bob", "password": "faux"})
    assert response.status_code == 401
