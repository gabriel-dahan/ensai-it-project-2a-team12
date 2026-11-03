# API DJU

API FastAPI de calcul des degrés-jours unifiés (DJU) : en un point, sur une région, un département ou un zonage personnel.

## Installation

Depuis la racine du dépôt :

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e "api[dev]"
```

## Configuration

Créer un fichier `.env` à la racine du dépôt :

```
POSTGRES_HOST=...
POSTGRES_PORT=5432
POSTGRES_DATABASE=...
POSTGRES_USER=...
POSTGRES_PASSWORD=...
POSTGRES_SCHEMA=...

JWT_SECRET=une-longue-chaine-secrete

UVICORN_HOST=0.0.0.0
UVICORN_PORT=5001
```

## Chargement des données

Les scripts du dossier `data/` téléchargent les données ouvertes (communes, relevés Météo-France), les nettoient puis les chargent dans PostgreSQL selon le schéma `data/init_db.sql`. `init_db.py` lit le même `.env`. Depuis la racine du dépôt, dans cet ordre :

```bash
pip install -r data/requirements.txt
python data/meteo.py          # relevés Météo-France -> raw_data/meteo_france_brut.parquet
python data/qualite_meteo.py  # comble les trous     -> raw_data/meteo_france_nettoye.parquet
python data/communes.py       # territoire           -> raw_data/regions, departements, communes.parquet
python data/init_db.py        # crée les tables (init_db.sql) et les remplit à partir des Parquet
```

`meteo.py` accepte une liste de départements (`python data/meteo.py 22 29 35 56`). `init_db.py` est relançable : les lignes déjà présentes sont ignorées. Les tests des scripts de données se lancent avec `pytest data/test_data.py`.

## Lancement

```bash
cd api/src
python main.py
```

La documentation interactive est sur http://localhost:5001/docs.

## Tests

```bash
cd api
python -m pytest
```

Les tests de `test/test_api.py` n'ont pas besoin de base : les services sont remplacés par de faux objets.
