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

Les scripts du dossier `data/` téléchargent les données ouvertes (communes, relevés Météo-France), les nettoient puis les chargent dans PostgreSQL selon le schéma `data/init_db.sql`. Ils lisent le même `.env`. Voir la docstring en tête de chaque script pour l'ordre et les options.

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
