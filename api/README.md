# DJU API

FastAPI application that computes Degree Days (DJU, *degrés-jours unifiés*): at a point, over a region, a department or a personal zoning.

## Installation

From the root of the repository:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e "api[dev]"
```

## Configuration

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
```

## Loading the data

The scripts of the `data/` folder download the open data (municipalities, Météo-France records), clean them and load them into PostgreSQL following the `data/init_db.sql` schema. `init_db.py` reads the same `.env`. From the root of the repository, in this order:

```bash
pip install -r data/requirements.txt
python data/meteo.py          # Météo-France records -> raw_data/meteo_france_brut.parquet
python data/qualite_meteo.py  # fills the gaps       -> raw_data/meteo_france_nettoye.parquet
python data/communes.py       # territory            -> raw_data/regions, departements, communes.parquet
python data/init_db.py        # creates the tables (init_db.sql) and fills them from the Parquet files
```

`meteo.py` accepts a list of departments (`python data/meteo.py 22 29 35 56`). `init_db.py` can be run again: rows already in the database are skipped. The tests of the data scripts are run with `pytest data/test_data.py`.

## Running

```bash
cd api/src
python main.py
```

The interactive documentation is available at http://localhost:5001/docs.

## Tests

```bash
cd api
python -m pytest
```

The tests in `test/test_api.py` do not need a database: the services are replaced by fake objects.
