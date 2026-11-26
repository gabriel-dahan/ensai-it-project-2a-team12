# DJU project: degree days from Météo-France data

This project computes **degree days** (DJU, *degrés-jours unifiés*) anywhere in France, from the daily records of Météo-France weather stations. Degree days measure how cold or hot a period was compared with a threshold temperature; they are used to analyse the energy consumption related to heating and cooling.

The project has two parts:

- a **data pipeline** (`data/`) that downloads the weather records and the French territory, cleans them and loads them into PostgreSQL;
- a **REST API** (`api/`, FastAPI) that computes DJU at a GPS point, over a department, a region or a zoning defined by a user. Its own README, [api/README.md](api/README.md), lists the routes and explains how to run, use and test it.

Project carried out by Team 12 as part of the second-year IT project at ENSAI.

## Contents

- [Features](#features)
- [How DJU are computed](#how-dju-are-computed)
- [Data](#data)
- [Repository structure](#repository-structure)
- [Getting started](#getting-started)
- [Loading the data](#loading-the-data)
- [Tests and code quality](#tests-and-code-quality)
- [Documentation](#documentation)

## Features

| Id | Feature |
|----|---------|
| F1 | DJU at a GPS point (latitude, longitude, optional altitude) |
| F2 | List of regions and departments, and the municipalities of each one |
| F3 | DJU over a department, a region or a personal zoning |
| F4 | Create, list, edit and delete personal zonings (lists of municipalities), with a user account |
| FO1 | Zone calculations are stored and read back when the same request comes again |
| FO2 | Results as JSON or CSV |
| FO3 | Import a zoning from a CSV or JSON file |

Calculations accept a heating and/or a cooling threshold, any period from 1990 onwards, a time step (day, week, month or year), the number of stations used and an altitude correction. Each result gives the DJU value, the number of days actually computed and the share of those days based only on observed (not filled-in) values.

The corresponding routes are listed in [api/README.md](api/README.md#routes).

## How DJU are computed

1. **Daily mean temperature** of a station: `(Tmin + Tmax) / 2`.
2. **Temperature at a location**: the *n* nearest stations that have records over the period, within 50 km, are selected (distances computed with the Haversine formula). Stations without any data on the period are skipped and replaced by the next nearest ones. Each day, the location temperature is the inverse distance weighted mean (weights `1 / d²`) of the stations that have a value that day.
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

The origin of each value is kept in the `SOURCE_TMIN` / `SOURCE_TMAX` columns, and loaded as the `observed` flag of each record. This is what the `observed_ratio` of the results is based on.

### Database

The schema is in [data/init_db.sql](data/init_db.sql):

| Tables | Content |
|--------|---------|
| `regions`, `departments`, `municipalities` | French territory (INSEE codes, town hall coordinates, altitude, population) |
| `meteo_stations`, `temperature_reports` | Météo-France stations and their daily `tmin` / `tmax`, with the origin of each value |
| `users`, `zonings`, `zoning_municipalities` | User accounts and personal zonings |
| `dju_types`, `dju_calculations`, `dju_results` | Stored zone calculations (cache) |

## Repository structure

```
.
├── README.md              this file: the project as a whole
├── .env.example           template of the .env file, shared by the API and the data scripts
├── api/                   the FastAPI application (see api/README.md)
│   ├── README.md
│   ├── pyproject.toml     dependencies, pytest, coverage and ruff settings
│   ├── src/               source code, one folder per layer
│   └── test/
├── data/                  data pipeline
│   ├── meteo.py           download of the Météo-France records
│   ├── qualite_meteo.py   outliers and missing values
│   ├── communes.py        download of regions, departments and municipalities
│   ├── init_db.sql        database schema
│   ├── init_db.py         creation and loading of the database
│   ├── data_visualisation.py
│   ├── test_data.py
│   ├── requirements.txt
│   └── raw_data/          generated Parquet files (not versioned)
└── doc/
    ├── reports/           interim and final reports (Quarto) and their diagrams
    ├── tracking/          weekly progress notes
    ├── new_diagram.md     current diagrams (Mermaid)
    └── archive_old/       first diagrams, kept for history only
```

## Getting started

Python 3.13 or later and a PostgreSQL database are required. From the root of the repository:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e "api[dev]"          # API, with pytest, httpx, ruff and coverage
pip install -r data/requirements.txt
cp .env.example .env               # then fill it in
```

The `.env` file is read from the root of the repository by both the API and the data scripts:

| Variable | Meaning |
|----------|---------|
| `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DATABASE`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | PostgreSQL connection |
| `POSTGRES_SCHEMA` | Schema that holds the tables |
| `JWT_SECRET` | Secret key used to sign login tokens (any long random string) |
| `UVICORN_HOST`, `UVICORN_PORT` | Address of the API (default `0.0.0.0:5001`) |

Then:

1. load the data into the database (next section), once;
2. start the API: `cd api/src && python main.py`, then open http://localhost:5001/docs. See [api/README.md](api/README.md) for the routes and examples.

## Loading the data

The scripts of the `data/` folder are run once, in this order, from the root of the repository:

| Script | Input | Output |
|--------|-------|--------|
| `python data/meteo.py` | Météo-France open data (data.gouv.fr) | `raw_data/meteo_france_brut.parquet` |
| `python data/qualite_meteo.py` | raw weather file | `raw_data/meteo_france_nettoye.parquet` (outliers removed, gaps filled) |
| `python data/communes.py` | `geo.api.gouv.fr`, IGN altimetry service | `raw_data/regions.parquet`, `departements.parquet`, `communes.parquet` |
| `python data/init_db.py` | Parquet files, `init_db.sql` | tables created and filled |

- `meteo.py` accepts a list of departments, e.g. `python data/meteo.py 22 29 35 56`; without arguments, all departments are downloaded. Downloads are saved per department, so an interrupted run can be resumed. For a quick test, one department is enough.
- `init_db.py` can be run again: rows already in the database are skipped.
- The generated Parquet files (several GB) are stored in `data/raw_data/`, which is not versioned.
- `python data/data_visualisation.py` prints a short summary of each Parquet file.

## Tests and code quality

```bash
pytest data/test_data.py       # 25 tests on the data scripts, from the root of the repository
cd api && python -m pytest     # 120 tests on the API (details in api/README.md)
```

No test needs a database or a network connection: the data are built by hand, and the database is replaced by fake objects.

The code is checked and formatted with [Ruff](https://docs.astral.sh/ruff/). The settings are in `api/pyproject.toml`, and `data/ruff.toml` reuses them. From the root of the repository:

```bash
ruff check api data      # lint (add --fix to fix what can be fixed automatically)
ruff format api data     # format
```

## Documentation

- [api/README.md](api/README.md): routes, use and architecture of the API;
- [doc/reports/final_report/](doc/reports/final_report/): final report (`main.qmd`, `main.pdf`). The diagrams are written in Mermaid in `resources/mermaid/` and turned into PNG with `python resources/render_diagrams.py` (needs Chrome and Pillow);
- [doc/reports/interim_report/](doc/reports/interim_report/): interim report and the annotated analysis report;
- [doc/tracking/](doc/tracking/): weekly progress notes.

The reports are rendered with `quarto render main.qmd` (XeLaTeX).

## Technologies

Python 3.13, FastAPI, Uvicorn, Pydantic, PostgreSQL (psycopg2), pandas, NumPy, PyArrow, requests, bcrypt, PyJWT, pytest, Ruff.

## Team 12

- Gabriel Dahan
- Eudes Sterlin
- Marceau Feral
- Gwenael Lassalle
- Mohamed Aziz Youssfi

## License

See [LICENSE](LICENSE).
