# DJU API

FastAPI application that computes degree days (DJU) from the weather records loaded in PostgreSQL. This README covers the API only: how to run it, its routes, its code and its tests. The project as a whole (calculation method, data, data pipeline) is described in the [main README](../README.md).

## Contents

- [Running the API](#running-the-api)
- [Routes](#routes)
- [Calculation parameters](#calculation-parameters)
- [Examples](#examples)
- [Errors](#errors)
- [Architecture](#architecture)
- [Code conventions](#code-conventions)
- [Tests and coverage](#tests-and-coverage)

## Running the API

Requirements: the virtual environment and the `.env` file described in the [main README](../README.md#getting-started), and a database filled by the data scripts.

```bash
pip install -e "api[dev]"    # from the root of the repository, if not done yet
cd api/src
python main.py
```

- Interactive documentation (Swagger): http://localhost:5001/docs. Every route can be tried from there.
- `GET /health` checks that the API is running and that the database answers: `{"status": "ok", "database": "ok"}`, or `503` with `"database": "unreachable"` (wrong `.env`, server down, VPN needed...).
- The first request after start-up takes about 10 s: the API reads the period covered by the records once and keeps it in memory.

## Routes

| Id | Route | Token | Description |
|----|-------|-------|-------------|
| F1 | `POST /dju/point` | No | DJU at a GPS point |
| F2 | `GET /zones?type=region\|department\|all` | No | Regions and/or departments (INSEE code and name) |
| F2 | `GET /zones/{region\|department}/{insee_code}` | No | A region or department with its municipalities |
| F3 | `POST /dju/zone` | Only for a zoning | DJU over a department, a region or a personal zoning |
| — | `POST /user/register` | No | Create an account |
| — | `POST /user/login` | No | Get a token |
| F4 | `GET /user/zones` | Yes | List my zonings |
| F4 | `POST /user/zones` | Yes | Create a zoning from a list of INSEE codes |
| F4 | `PATCH /user/zones/{id}` | Yes | Change the description, add or remove municipalities |
| F4 | `DELETE /user/zones/{id}` | Yes | Delete a zoning |
| FO3 | `POST /user/zones/import` | Yes | Create a zoning from the content of a CSV or JSON file |
| — | `GET /health` | No | State of the API and of the database |

`POST /dju/point` and `POST /dju/zone` return JSON by default, or CSV with `?format=csv` (FO2).

**Authentication.** Call `POST /user/login`, then send the token in the `Authorization: Bearer <token>` header. Tokens are valid for 24 hours. Usernames have 3 to 50 characters, passwords 8 characters to 72 bytes; passwords are stored as bcrypt hashes.

**Zoning import (FO3).** The request body holds the file name (`.csv` or `.json`, which decides how the content is read), the file content as text, and optionally a name (the file name by default) and a description:

- CSV: `,` or `;` separator; the `code_insee` column if there is one, otherwise the first column; a header line is optional;
- JSON: a list of codes `["35238", "35047"]` or an object `{"codes_insee": [...]}`.

## Calculation parameters

| Field | Routes | Default | Meaning |
|-------|--------|---------|---------|
| `start_date`, `end_date` | both | required | Period (`YYYY-MM-DD`). A period that goes beyond the data is shortened, with a `warning` |
| `heating_threshold`, `cooling_threshold` | both | — | Thresholds in °C; at least one is required, both give two series of results |
| `time_step` | both | `day` | `day`, `week` (ISO week, Monday to Sunday), `month` or `year` |
| `number_of_stations` | both | `3` | 1 to 10 nearest stations, within 50 km |
| `latitude`, `longitude` | point | required | Location in degrees |
| `altitude` | point | — | Altitude in metres; when given, temperatures are corrected for altitude |
| `zone_type` | zone | required | `department`, `region` or `zoning` |
| `zone_code` | zone | required | INSEE code (`35`, `53`, `2A`) or zoning id |
| `aggregation_level` | zone | `zone` | One result for the whole zone, per `department` (regions only) or per `municipality` |
| `use_altitude` | zone | `true` | Altitude correction at each town hall |

Each result gives `period_start`, `period_end`, `value` (DJU of the period), `days_with_data` (days actually computed) and `observed_ratio` (share of those days computed only from observed values, the rest coming from filled-in values). A point response also lists the stations used, with their distance, and includes a `warning` when fewer stations than requested are found within 50 km.

Zone calculations are stored in the database and read back when the same request comes again (FO1). Editing or deleting a zoning removes its stored calculations, so a result is never out of date.

## Examples

**Heating degree days in Rennes, month by month**, from the 2 nearest stations:

```bash
curl -X POST "http://localhost:5001/dju/point" \
  -H "Content-Type: application/json" \
  -d '{"latitude": 48.11, "longitude": -1.68, "start_date": "2024-01-01",
       "end_date": "2024-03-31", "heating_threshold": 18, "time_step": "month",
       "number_of_stations": 2}'
```

```json
{
  "results": {
    "heating": [
      {"period_start": "2024-01-01", "period_end": "2024-01-31", "value": 373.79, "days_with_data": 31, "observed_ratio": 1.0},
      {"period_start": "2024-02-01", "period_end": "2024-02-29", "value": 232.12, "days_with_data": 29, "observed_ratio": 1.0},
      {"period_start": "2024-03-01", "period_end": "2024-03-31", "value": 255.12, "days_with_data": 31, "observed_ratio": 1.0}
    ]
  },
  "stations": [
    {"station_code": "35238003", "name": "RENNES GALLET", "latitude": 48.126167, "longitude": -1.6435, "altitude": 66.0, "distance_km": 3.3},
    {"station_code": "35281001", "name": "RENNES-ST JACQUES", "latitude": 48.068833, "longitude": -1.734, "altitude": 36.0, "distance_km": 6.1}
  ],
  "warning": null
}
```

(values rounded here; the API returns them unrounded)

**DJU of a department over a year, as CSV** (`35` is the INSEE code of Ille-et-Vilaine, given by `GET /zones?type=department`):

```bash
curl -X POST "http://localhost:5001/dju/zone?format=csv" \
  -H "Content-Type: application/json" \
  -d '{"zone_type": "department", "zone_code": "35", "start_date": "2024-01-01",
       "end_date": "2024-12-31", "heating_threshold": 18, "time_step": "year"}'
```

```
zone,zone_code,mode,period_start,period_end,value,days_with_data,observed_ratio
Ille-et-Vilaine,35,heating,2024-01-01,2024-12-31,2047.0005153821294,366,1.0
```

Add `"aggregation_level": "municipality"` to get one line per municipality.

**Personal zoning**: create an account, log in, create a zoning, then compute its DJU:

```bash
curl -X POST http://localhost:5001/user/register -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "a-strong-password"}'

TOKEN=$(curl -s -X POST http://localhost:5001/user/login -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "a-strong-password"}' | python -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

curl -X POST http://localhost:5001/user/zones -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Rennes area", "codes_insee": ["35238", "35047", "35051"]}'
# -> {"id": 12, ...}

curl -X POST http://localhost:5001/dju/zone -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"zone_type": "zoning", "zone_code": "12", "start_date": "2024-01-01",
       "end_date": "2024-12-31", "heating_threshold": 18, "time_step": "year"}'
```

## Errors

Errors are returned as `{"detail": "..."}` with the following codes:

| Code | When |
|------|------|
| `400` | No threshold, dates in the wrong order, unknown INSEE codes, unreadable import file... |
| `401` | Missing, invalid or expired token; wrong username or password |
| `403` | Zoning owned by another user |
| `404` | Unknown zone or zoning; no station within 50 km of the point (at sea, outside France) |
| `409` | Username already taken |
| `422` | Request body that does not match the schema (checked by Pydantic) |
| `503` | `/health` only: the database does not answer |

## Architecture

The code follows the layered architecture of the ENSAI second-year IT project template. Each layer only calls the layers below it:

```
controllers  →  service  →  dao  →  PostgreSQL
     │             │         │
     └─ schema     └─────────┴──→  business_object
```

```
api/src/
├── main.py            entry point (FastAPI app, routers, /health)
├── controllers/       routes, authentication dependencies, CSV export
├── schema/            Pydantic request and response models
├── service/           business logic (DJU, temperatures, zones, authentication)
├── business_object/   DJU calculation, zones, weather stations, users
├── dao/               PostgreSQL access (psycopg2)
└── utils/             singleton metaclass
```

| Layer | Files | Role |
|-------|-------|------|
| `controllers/` | `dju_controller.py`, `zone_controller.py`, `user_controller.py`, `dependencies.py` | Read the request, call a service, build the JSON or CSV response. Turn a `ServiceError` into an HTTP error |
| `schema/` | `dju_schema.py`, `zone_schema.py`, `user_schema.py` | Pydantic models: validation of the input values |
| `service/` | `dju_service.py`, `temperature_service.py`, `zone_service.py`, `auth_service.py`, `errors.py` | Business rules: checks, choice of stations, cache, ownership of zonings |
| `business_object/` | `dju.py`, `geo_zone.py`, `meteo_station.py`, `user.py` | Domain classes, without database access |
| `dao/` | `db_connection.py`, `dju_dao.py`, `geo_zone_dao.py`, `meteo_station_dao.py`, `temperature_report_dao.py`, `user_dao.py`, `zoning_dao.py` | SQL queries; return business objects |

### Main classes

- `DBConnection` (singleton): the only PostgreSQL connection, reopened automatically if the server closed it.
- DAOs (singletons): one per table or group of tables. `MeteoStationDao` keeps all stations in memory after the first read.
- `TemperatureService`: finds the nearest stations with data and estimates the daily temperature of one or many places (inverse distance weighting, altitude correction).
- `DjuService`: checks the request, shortens the period to the available data, runs one `DjuCalculation` per threshold and, for zones, reads or fills the cache.
- `ZoneService`: official zones, personal zonings (create, import, edit, delete) and ownership checks.
- `AuthService`: accounts, password check and JWT tokens.
- `DjuCalculation`: computes daily DJU from temperatures (`run` for a point, `run_for_zone` for a zone weighted by population), then sums them by period (`aggregate`).

### Path of a request: `POST /dju/point`

1. `dju_controller.calculate_point_dju` receives a `DjuPointRequest` already validated by Pydantic.
2. `DjuService.calculate_point_dju` checks the thresholds and dates and shortens the period to the data in the database.
3. `TemperatureService.find_candidate_stations` picks the *n* nearest stations with records on the period; `estimate_daily_temperatures` builds one temperature per day.
4. For each threshold, a `DjuCalculation` is created and `run` computes the results.
5. The controller turns the calculations into a `DjuResponse` (or CSV), with the stations used and the warnings.

`POST /dju/zone` follows the same path, but first looks for the same calculation in the database (`DjuDao.find_calculation`) and saves new results afterwards.

### Dependency injection

Services receive their dependencies in their constructor and only create the real ones when nothing is given:

```python
class DjuService:
    def __init__(self, temperature_service=None, zone_service=None, dju_dao=None):
        self.temperature_service = temperature_service or TemperatureService()
        ...
```

This is what lets the tests replace the DAOs with fake objects, without a database.

## Code conventions

- Identifiers in English; docstrings and comments in French.
- Every module, class and public function has a docstring, in one line when possible; comments explain a choice rather than repeat the code.
- Routes are plain `def` functions, not `async def`, because psycopg2 is blocking (`test_routes_are_not_async` checks it).
- Errors the user can cause (bad dates, unknown zone, zoning of someone else...) are raised in the services as `ServiceError(message, status_code)`, never as `HTTPException`.
- Code checked with `ruff check` and formatted with `ruff format` (settings in `pyproject.toml`: lines of 100 characters, rules `E`, `F`, `W`, `I`, `B`, `UP`).

To add a route: models in `schema/`, logic in a service method, SQL in a DAO if needed, route in a controller (with `Depends(get_current_user)` if a token is required), then a test with a fake service in `test_api.py` and a test with fake DAOs in `test_services.py`.

## Tests and coverage

From the `api/` folder:

```bash
python -m pytest
```

| File | Tests | What is tested |
|------|------:|----------------|
| `test/test_business_objects.py` | 25 | DJU formula, aggregation by period, weighting by population, zones, users |
| `test/test_services.py` | 53 | Services with fake DAOs: choice of stations, altitude, cache, zonings, authentication, error codes |
| `test/test_api.py` | 42 | Routes with fake services (`TestClient`): status codes, Pydantic validation, JSON and CSV output, tokens |

No test needs a database or a network connection.

Coverage (settings in `pyproject.toml`):

```bash
coverage run -m pytest
coverage report          # summary in the terminal
coverage html            # detailed report in coverage_report/
```

The DAOs are little covered: they only run SQL queries and were checked by hand on the real database.
