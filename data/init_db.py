"""Crée les tables (init_db.sql) et les remplit à partir des fichiers Parquet.

Fichiers lus dans data/raw_data :
    - communes.parquet (communes.py) -> regions, departments, municipalities ;
    - meteo_france_1990_2026_nettoye.parquet (qualite_meteo.py) -> meteo_stations,
      temperature_reports.

Les autres tables (users, zonings, cache des calculs) sont remplies par l'API.
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import pandas as pd
import psycopg2
from dotenv import load_dotenv
from psycopg2 import sql
from psycopg2.extras import execute_values

DATA_DIR = Path(__file__).resolve().parent
ROOT_DIR = DATA_DIR.parent
SQL_FILE = DATA_DIR / "init_db.sql"
PARQUET_COMMUNES = DATA_DIR / "raw_data" / "communes.parquet"
PARQUET_METEO = DATA_DIR / "raw_data" / "meteo_france_1990_2026_nettoye.parquet"

TAILLE_LOT_RELEVES = 1_000_000


def _load_env() -> None:
    load_dotenv(ROOT_DIR / ".env")


def _connect():
    return psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DATABASE"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def _ensure_schema(conn) -> None:
    schema = os.environ["POSTGRES_SCHEMA"]
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                sql.Identifier(schema)
            )
        )
        cur.execute(
            sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
        )
    conn.commit()


def create_tables(conn) -> None:
    """Execute DDL from init_db.sql inside the configured schema."""
    ddl = SQL_FILE.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(ddl)
    conn.commit()
    print(f"Tables créées via {SQL_FILE.name}.")


def _lignes(df: pd.DataFrame) -> list[tuple]:
    """Convertit un DataFrame en tuples de valeurs Python (NaN -> None) pour psycopg2."""
    df = df.astype(object).where(df.notna(), None)
    return [tuple(ligne) for ligne in df.to_numpy()]


def _ids_par_code(conn, table: str, colonne_code: str) -> dict:
    """Renvoie {code: id} pour une table déjà remplie (ex : {"35": 12} pour departments)."""
    with conn.cursor() as cur:
        cur.execute(f"SELECT id, {colonne_code} FROM {table}")
        return {code: id_ for id_, code in cur.fetchall()}


def charger_territoire(conn, communes: pd.DataFrame) -> None:
    """Remplit regions, departments puis municipalities.

    Chaque table a besoin des id de la précédente pour ses clés étrangères.
    """
    regions = communes[["Region", "Nom_Region"]].drop_duplicates("Region")
    with conn.cursor() as cur:
        execute_values(cur, "INSERT INTO regions (insee_code, name) VALUES %s", _lignes(regions))
    id_regions = _ids_par_code(conn, "regions", "insee_code")

    departements = communes[["Dept", "Nom_Dept", "Region"]].drop_duplicates("Dept").copy()
    departements["Region"] = departements["Region"].map(id_regions)
    with conn.cursor() as cur:
        execute_values(
            cur,
            "INSERT INTO departments (insee_code, name, region_id) VALUES %s",
            _lignes(departements),
        )
    id_departements = _ids_par_code(conn, "departments", "insee_code")

    municipalites = communes[
        ["Code_Insee", "Commune", "Lat", "Lon", "Altitude", "Population", "Dept"]
    ].copy()
    municipalites["Dept"] = municipalites["Dept"].map(id_departements)
    with conn.cursor() as cur:
        execute_values(
            cur,
            "INSERT INTO municipalities "
            "(insee_code, name, latitude, longitude, altitude, population, department_id) "
            "VALUES %s",
            _lignes(municipalites),
            page_size=1_000,
        )
    conn.commit()
    print(
        f"{len(regions)} régions, {len(departements)} départements "
        f"et {len(municipalites)} communes insérés."
    )


def charger_stations(conn, meteo: pd.DataFrame) -> dict:
    """Remplit meteo_stations, une ligne par station avec ses dernières coordonnées connues.

    Returns:
        Dictionnaire {NUM_POSTE: id de la station en base}.
    """
    stations = meteo.sort_values(["NUM_POSTE", "DATE"]).drop_duplicates("NUM_POSTE", keep="last")
    stations = stations[["NUM_POSTE", "NOM_USUEL", "LAT", "LON", "ALTI"]]
    with conn.cursor() as cur:
        execute_values(
            cur,
            "INSERT INTO meteo_stations (station_code, name, latitude, longitude, altitude) "
            "VALUES %s",
            _lignes(stations),
        )
    conn.commit()
    print(f"{len(stations)} stations insérées.")
    return _ids_par_code(conn, "meteo_stations", "station_code")


def charger_releves(conn, meteo: pd.DataFrame, id_stations: dict) -> None:
    """Remplit temperature_reports par lots, avec COPY.

    COPY est beaucoup plus rapide qu'INSERT pour les dizaines de millions de
    relevés. Les jours sans aucune température (trous de plus de 30 jours) ne
    sont pas insérés.
    """
    releves = meteo.dropna(subset=["TMIN", "TMAX"], how="all")
    releves = pd.DataFrame(
        {
            "station_id": releves["NUM_POSTE"].map(id_stations),
            "date": releves["DATE"],
            "temp_min": releves["TMIN"],
            "temp_max": releves["TMAX"],
            "source_tmin": releves["SOURCE_TMIN"],
            "source_tmax": releves["SOURCE_TMAX"],
        }
    )

    requete = (
        "COPY temperature_reports "
        "(station_id, date, temp_min, temp_max, source_tmin, source_tmax) "
        "FROM STDIN WITH CSV"
    )
    with conn.cursor() as cur:
        for debut in range(0, len(releves), TAILLE_LOT_RELEVES):
            lot = releves.iloc[debut : debut + TAILLE_LOT_RELEVES]
            # Le lot est écrit en CSV en mémoire ; une case vide devient NULL en base
            tampon = io.StringIO()
            lot.to_csv(tampon, index=False, header=False, date_format="%Y-%m-%d")
            tampon.seek(0)
            cur.copy_expert(requete, tampon)
            print(f"Relevés insérés : {debut + len(lot)} / {len(releves)}")
    conn.commit()


def main() -> None:
    _load_env()
    print("Lecture des fichiers Parquet...")
    communes = pd.read_parquet(PARQUET_COMMUNES)
    meteo = pd.read_parquet(PARQUET_METEO)

    print("Connexion à PostgreSQL...")
    conn = _connect()
    try:
        _ensure_schema(conn)
        create_tables(conn)
        charger_territoire(conn, communes)
        id_stations = charger_stations(conn, meteo)
        charger_releves(conn, meteo, id_stations)
        print("Initialisation de la base terminée.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
