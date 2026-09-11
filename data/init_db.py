"""Create database tables and load open-data into PostgreSQL."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import psycopg2
from dotenv import load_dotenv
from psycopg2 import sql
from psycopg2.extras import execute_values

from communes import fetch_communes
from meteo_stations import fetch_meteo_data

DATA_DIR = Path(__file__).resolve().parent
ROOT_DIR = DATA_DIR.parent
SQL_FILE = DATA_DIR / "init_db.sql"

COMMUNE_INSERT = """
    INSERT INTO communes (
        nom, code_postal, code_departement, code_region,
        longitude, latitude, altitude
    ) VALUES %s
"""

METEO_INSERT = """
    INSERT INTO meteo_observations (
        num_poste, date, nom_usuel,
        tmin, tmax, tmean,
        latitude, longitude, altitude, tmed_tn_tx
    ) VALUES %s
"""

METEO_BATCH_SIZE = 5000


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
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema))
        )
        cur.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
    conn.commit()


def create_tables(conn) -> None:
    """Execute DDL from init_db.sql inside the configured schema."""
    ddl = SQL_FILE.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(ddl)
    conn.commit()
    print(f"Tables créées via {SQL_FILE.name}.")


def _none_if_na(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def insert_communes(conn, rows: list[dict]) -> None:
    values = [
        (
            row.get("Commune"),
            row.get("Code_Postal") or None,
            row.get("Dept"),
            row.get("Region"),
            _none_if_na(row.get("Lon")),
            _none_if_na(row.get("Lat")),
            _none_if_na(row.get("Altitude")),
        )
        for row in rows
    ]
    with conn.cursor() as cur:
        execute_values(cur, COMMUNE_INSERT, values, page_size=1_000)
    conn.commit()
    print(f"{len(values)} communes insérées.")


def insert_meteo_observations(conn, df: pd.DataFrame) -> None:
    if df.empty:
        print("Aucune observation météo à insérer.")
        return

    work = df.copy()
    work["DATE"] = pd.to_datetime(work["DATE"].astype(str), format="%Y%m%d", errors="coerce")
    work = work.dropna(subset=["NUM_POSTE", "DATE"])

    columns = [
        "NUM_POSTE",
        "DATE",
        "NOM_USUEL",
        "TMIN",
        "TMAX",
        "TMEAN",
        "LAT",
        "LON",
        "ALTI",
        "TMED_TN_TX",
    ]
    for col in columns:
        if col not in work.columns:
            work[col] = None

    total = 0
    with conn.cursor() as cur:
        for start in range(0, len(work), METEO_BATCH_SIZE):
            chunk = work.iloc[start : start + METEO_BATCH_SIZE][columns]
            values = [
                (
                    str(num_poste),
                    date_val.date(),
                    _none_if_na(nom_usuel),
                    _none_if_na(tmin),
                    _none_if_na(tmax),
                    _none_if_na(tmean),
                    _none_if_na(lat),
                    _none_if_na(lon),
                    _none_if_na(alti),
                    _none_if_na(tmed),
                )
                for num_poste, date_val, nom_usuel, tmin, tmax, tmean, lat, lon, alti, tmed in chunk.itertuples(
                    index=False, name=None
                )
            ]
            execute_values(cur, METEO_INSERT, values, page_size=METEO_BATCH_SIZE)
            total += len(values)
            print(f"Observations météo insérées : {total} / {len(work)}")

    conn.commit()
    print(f"{total} observations météo insérées.")


def main() -> None:
    _load_env()
    print("Connexion à PostgreSQL...")
    conn = _connect()

    try:
        _ensure_schema(conn)
        create_tables(conn)

        print("Téléchargement des communes...")
        communes = fetch_communes()
        insert_communes(conn, communes)

        print("Téléchargement des données météo (peut être long)...")
        meteo_df = fetch_meteo_data()
        insert_meteo_observations(conn, meteo_df)

        print("Initialisation de la base terminée.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
