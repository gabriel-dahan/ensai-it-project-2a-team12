# DJU API

A FastAPI application that computes **Degree Days** (DJU, *degrés-jours unifiés*) from Météo-France weather records, for a GPS point, a French department or region, or a user-defined zoning.

Degree days measure how cold or hot a period was compared with a threshold temperature. They are used to analyse the energy consumption related to heating and cooling.

Project carried out by Team 12 as part of the second-year IT project at ENSAI.

## Features

| Id | Feature | Route |
|----|---------|-------|
| F1 | DJU at a GPS point (latitude, longitude, optional altitude) | `POST /dju/point` |
| F2 | List of regions and departments, and the municipalities of each one | `GET /zones`, `GET /zones/{type}/{insee_code}` |
| F3 | DJU over a department, a region or a personal zoning | `POST /dju/zone` |
| F4 | Create, list, edit and delete personal zonings (lists of municipalities) | `/user/zones` |
| FO3 | Import a zoning from a CSV or JSON file | `POST /user/zones/import` |
| — | Account creation and login (JWT) | `POST /user/register`, `POST /user/login` |

Calculation options:

- heating threshold and/or cooling threshold (at least one is required);
- any period covered by the data, from 1990 onwards; a period that goes beyond the available data is shortened and the response includes a `warning`;
- time step: `day`, `week` (ISO week, Monday to Sunday), `month` or `year`;
- number of nearby weather stations used (1 to 10, default 3);
- altitude correction (on by default for zones, applied at a point when an altitude is given);
- for a zone, results for the whole zone, per department (regions only) or per municipality;
- JSON output by default, or CSV with `?format=csv`.

Each result gives the DJU value of the period, the number of days actually computed (`days_with_data`) and the share of those days based only on observed values (`observed_ratio`), the rest coming from filled-in values.

Zone calculations are stored in the database and read back when the same request comes again. Editing or deleting a zoning removes its stored calculations.

## How DJU are computed

1. **Daily mean temperature** of a station: `(Tmin + Tmax) / 2`.
2. **Temperature at a location**: the *n* nearest stations that have records over the period are selected (distances computed with the Haversine formula). Stations without any data on the period are skipped and replaced by the next nearest ones. Each day, the location temperature is the inverse distance weighted mean (weights `1 / d²`) of the stations that have a value that day.
3. **Altitude correction**: each station temperature is shifted by −0.65 °C per 100 m of altitude difference between the location and the station.
4. **Daily DJU**: `max(0, threshold − T)` for heating, `max(0, T − threshold)` for cooling.
5. **Zones**: the temperature of each municipality is estimated at its town hall, its daily DJU computed, then averaged over the municipalities of the zone, weighted by population (equal weights if no population is known).
6. **Aggregation**: daily values are summed by week, month or year. Periods at the edges are cut to the requested dates.

## Data

The data are downloaded from open data sources:

- **Weather**: daily records of all Météo-France stations since 1990 (`TN`, `TX`, station coordinates and altitude), from the Météo-France open data repository on data.gouv.fr;
- **Territory**: regions, departments and municipalities from `geo.api.gouv.fr` (town hall coordinates, or the municipality centre when the town hall is missing, and population), with the altitude of each municipality from the IGN altimetry service.

### Data cleaning

`data/qualite_meteo.py` prepares the weather records before they are loaded:

- temperatures outside [−50 ; 50] °C are removed as outliers;
- stations that only measure rainfall are removed;
- missing days are filled depending on the gap length:
  - 1 to 2 days: linear interpolation;
  - 3 to 7 days: 70 % local trend + 30 % mean of nearby stations, corrected by their usual difference with the station;
  - 8 to 30 days: linear regression on nearby stations that have measurements throughout the gap;
  - more than 30 days: not filled;
- nearby stations are the 5 closest stations within 50 km, so an isolated station may have fewer neighbours, or none;
- a filled value that gives `Tmin > Tmax` is removed.

The origin of each value is kept in the `SOURCE_TMIN` / `SOURCE_TMAX` columns, and loaded as the `observed` flag of each record. This is what `observed_ratio` is based on.

## Architecture

The application follows a layered architecture, based on the ENSAI second-year IT project template:

```
api/src/
├── main.py            entry point (FastAPI app, routers, /health)
├── controllers/       routes, authentication dependencies, CSV export
├── schema/            Pydantic request and response models
├── service/           business logic (DJU, temperatures, zones, authentication)
├── business_object/   DJU calculation, zones, stations, temperature records, users
├── dao/               PostgreSQL access (psycopg2)
└── utils/             singleton for the database connection
```

| Layer | Files |
|-------|-------|
| business_object | `dju.py`, `geo_zone.py`, `meteo_station.py`, `temperature_report.py`, `user.py` |
| dao | `db_connection.py`, `dju_dao.py`, `geo_zone_dao.py`, `meteo_station_dao.py`, `temperature_report_dao.py`, `user_dao.py`, `zoning_dao.py` |
| service | `auth_service.py`, `dju_service.py`, `errors.py`, `temperature_service.py`, `zone_service.py` |
| controllers | `dependencies.py`, `dju_controller.py`, `user_controller.py`, `zone_controller.py` |
| schema | `dju_schema.py`, `user_schema.py`, `zone_schema.py` |

The database schema is in [data/init_db.sql](data/init_db.sql): users, regions, departments, municipalities, zonings, weather stations, temperature records, DJU types, calculations and results.

## Installation

Python 3.13 or later and a PostgreSQL database are required. From the root of the repository:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e "api[dev]"
pip install -r data/requirements.txt
```

Create a `.env` file at the root of the repository:

```
POSTGRES_HOST=...
POSTGRES_PORT=5432
POSTGRES_DATABASE=...
POSTGRES_USER=...
POSTGRES_PASSWORD=...
POSTGRES_SCHEMA=...

JWT_SECRET=a-long-secret-string

UVICORN_HOST=0.0.0.0
UVICORN_PORT=5001
# ROOT_PATH=/prefix   (optional, when the API is served behind a proxy)
```

## Loading the data

The scripts of the `data/` folder are run once, in this order, from the root of the repository:

```bash
python data/meteo.py          # Météo-France records    -> raw_data/meteo_france_brut.parquet
python data/qualite_meteo.py  # outliers and gaps       -> raw_data/meteo_france_nettoye.parquet
python data/communes.py       # regions, departments, municipalities -> raw_data/*.parquet
python data/init_db.py        # creates the tables (init_db.sql) and fills them from the Parquet files
```

- `meteo.py` accepts a list of departments, e.g. `python data/meteo.py 22 29 35 56`; without arguments, all departments are downloaded. Downloads are saved per department, so an interrupted run can be resumed.
- `init_db.py` reads the same `.env` and can be run again: rows already in the database are skipped.
- The generated Parquet files (several GB) are stored in `data/raw_data/`, which is not versioned.
- `data_visualisation.py` prints a short summary of each Parquet file.

## Running the API

```bash
cd api/src
python main.py
```

The interactive documentation (Swagger) is available at http://localhost:5001/docs. `GET /health` checks that the API is running.

Routes under `/user/zones` require a token: call `POST /user/login`, then send `Authorization: Bearer <token>`. Tokens are valid for 24 hours. Passwords must be 8 characters to 72 bytes long.

Example:

```bash
curl -X POST "http://localhost:5001/dju/point?format=json" \
  -H "Content-Type: application/json" \
  -d '{"latitude": 48.11, "longitude": -1.68, "start_date": "2024-01-01",
       "end_date": "2024-12-31", "heating_threshold": 18, "time_step": "month"}'
```

## Tests

```bash
cd api && python -m pytest     # API, services and business objects
pytest data/test_data.py       # data scripts, from the root of the repository
```

None of these tests need a database or a network connection: the DAOs and services are replaced by fake objects.

## Documentation

- [doc/reports/final_report/](doc/reports/final_report/): final report (`main.qmd`, `main.pdf`) and its diagrams;
- [doc/reports/interim_report/](doc/reports/interim_report/): interim report;
- [doc/tracking/](doc/tracking/): weekly progress notes.

## Technologies

Python 3.13, FastAPI, Uvicorn, Pydantic, PostgreSQL (psycopg2), pandas, NumPy, PyArrow, bcrypt, PyJWT, pytest, Ruff.

## Team 12

- Gabriel Dahan
- Eudes Sterlin
- Marceau Feral
- Gwenael Lassalle
- Mohamed Aziz Youssfi

## License

See [LICENSE](LICENSE).
