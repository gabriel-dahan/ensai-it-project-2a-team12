"""Crée les tables (init_db.sql) puis les remplit à partir des fichiers Parquet.

Relançable : les lignes déjà présentes sont ignorées (ON CONFLICT DO NOTHING).
"""

import io
import os
from pathlib import Path

import pandas as pd
import psycopg2
from dotenv import load_dotenv
from psycopg2 import sql
from psycopg2.extras import execute_values

DATA_DIR = Path(__file__).resolve().parent
RAW_DIR = DATA_DIR / "raw_data"
SQL_FILE = DATA_DIR / "init_db.sql"
TAILLE_LOT = 500_000  # relevés envoyés par COPY


def connecter():
    """Connexion PostgreSQL avec le schéma du .env comme search_path."""
    load_dotenv(DATA_DIR.parent / ".env")
    conn = psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DATABASE"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )
    schema = sql.Identifier(os.environ["POSTGRES_SCHEMA"])
    with conn.cursor() as cur:
        cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(schema))
        cur.execute(sql.SQL("SET search_path TO {}").format(schema))
    conn.commit()
    return conn


def creer_tables(conn) -> None:
    """Exécute init_db.sql."""
    with conn.cursor() as cur:
        cur.execute(SQL_FILE.read_text(encoding="utf-8"))
    conn.commit()
    print("Tables créées.")


def sans_nan(valeur):
    """Remplace NaN / NA par None pour psycopg2."""
    return None if pd.isna(valeur) else valeur


def entier(valeur):
    """Convertit en int Python (None si absent)."""
    return None if pd.isna(valeur) else int(valeur)


def inserer(conn, table: str, colonnes: list[str], lignes: list[tuple]) -> None:
    """Insère des lignes en ignorant celles déjà présentes."""
    requete = f"INSERT INTO {table} ({', '.join(colonnes)}) VALUES %s ON CONFLICT DO NOTHING"
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        avant = cur.fetchone()[0]
        execute_values(cur, requete, lignes, page_size=5000)
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        apres = cur.fetchone()[0]
    conn.commit()
    print(f"{table} : {len(lignes):,} lignes lues, {apres - avant:,} nouvelles, {apres:,} au total")


def ids_par_code(conn, table: str, colonne: str) -> dict[str, int]:
    """Dictionnaire {code: id} d'une table."""
    with conn.cursor() as cur:
        cur.execute(f"SELECT {colonne}, id FROM {table}")
        return dict(cur.fetchall())


def inserer_regions(conn) -> None:
    """Régions."""
    df = pd.read_parquet(RAW_DIR / "regions.parquet")
    lignes = [(r.code, r.nom) for r in df.itertuples()]
    inserer(conn, "regions", ["insee_code", "name"], lignes)


def inserer_departements(conn) -> None:
    """Départements (rattachés à leur région)."""
    df = pd.read_parquet(RAW_DIR / "departements.parquet")
    regions = ids_par_code(conn, "regions", "insee_code")
    lignes = [(d.code, d.nom, regions[d.codeRegion]) for d in df.itertuples() if d.codeRegion in regions]
    inserer(conn, "departments", ["insee_code", "name", "region_id"], lignes)


def inserer_communes(conn) -> None:
    """Communes (celles d'un département inconnu sont ignorées)."""
    df = pd.read_parquet(RAW_DIR / "communes.parquet")
    departements = ids_par_code(conn, "departments", "insee_code")
    inconnues = ~df["codeDepartement"].isin(departements.keys())
    if inconnues.any():
        print(f"{inconnues.sum()} communes ignorées (département inconnu)")
    lignes = [
        (
            c.code,
            c.nom,
            c.latitude,
            c.longitude,
            sans_nan(c.altitude),
            entier(c.population),
            departements[c.codeDepartement],
        )
        for c in df[~inconnues].itertuples()
    ]
    colonnes = ["insee_code", "name", "latitude", "longitude", "altitude", "population", "department_id"]
    inserer(conn, "municipalities", colonnes, lignes)


def inserer_stations(conn, meteo: pd.DataFrame) -> None:
    """Une station par NUM_POSTE."""
    stations = meteo.drop_duplicates("NUM_POSTE").dropna(subset=["LAT", "LON"])
    lignes = [
        (s.NUM_POSTE, sans_nan(s.NOM_USUEL), s.LAT, s.LON, sans_nan(s.ALTI))
        for s in stations.itertuples()
    ]
    inserer(conn, "meteo_stations", ["station_code", "name", "latitude", "longitude", "altitude"], lignes)


def inserer_releves(conn, meteo: pd.DataFrame) -> None:
    """COPY dans une table temporaire, puis INSERT ... ON CONFLICT DO NOTHING, par lots."""
    colonnes = ["NUM_POSTE", "DATE", "TMIN", "TMAX", "SOURCE_TMIN", "SOURCE_TMAX"]
    with conn.cursor() as cur:
        # La table temporaire est vidée à chaque commit
        cur.execute(
            """
            CREATE TEMP TABLE IF NOT EXISTS releves_tmp (
                station_code VARCHAR(20), date DATE,
                temp_min DOUBLE PRECISION, temp_max DOUBLE PRECISION,
                source_tmin VARCHAR(32), source_tmax VARCHAR(32)
            ) ON COMMIT DELETE ROWS
            """
        )
    conn.commit()

    total, nouvelles = len(meteo), 0
    for debut in range(0, total, TAILLE_LOT):
        lot = meteo.iloc[debut : debut + TAILLE_LOT][colonnes]
        tampon = io.StringIO()
        lot.to_csv(tampon, index=False, header=False, date_format="%Y-%m-%d")
        tampon.seek(0)
        with conn.cursor() as cur:
            cur.copy_expert("COPY releves_tmp FROM STDIN WITH (FORMAT csv)", tampon)
            cur.execute(
                """
                INSERT INTO temperature_reports
                    (station_id, date, temp_min, temp_max, source_tmin, source_tmax)
                SELECT s.id, t.date, t.temp_min, t.temp_max, t.source_tmin, t.source_tmax
                FROM releves_tmp t
                JOIN meteo_stations s ON s.station_code = t.station_code
                ON CONFLICT (station_id, date) DO NOTHING
                """
            )
            nouvelles += cur.rowcount
        conn.commit()
        print(f"temperature_reports : {min(debut + TAILLE_LOT, total):,} / {total:,} lignes lues")
    print(f"temperature_reports : {nouvelles:,} nouvelles lignes")


def main() -> None:
    conn = connecter()
    try:
        creer_tables(conn)
        inserer_regions(conn)
        inserer_departements(conn)
        inserer_communes(conn)

        print("Lecture des relevés nettoyés...")
        meteo = pd.read_parquet(RAW_DIR / "meteo_france_nettoye.parquet")
        inserer_stations(conn, meteo)
        inserer_releves(conn, meteo)
        print("Base prête.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
