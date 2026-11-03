"""Télécharge les relevés quotidiens Météo-France (1990-2026) et écrit le Parquet brut.

Usage : python init_db.py [départements...]   (ex. python init_db.py 22 29 35 56)
Sans argument, tous les départements sont traités.
"""

import sys
from pathlib import Path

import pandas as pd
import requests

DOSSIER_DESTINATION = Path(__file__).resolve().parent / "raw_data"
FICHIER_BRUT = DOSSIER_DESTINATION / "meteo_france_brut.parquet"
URL_BASE = "https://meteofrance.s3.sbg.io.cloud.ovh.net/data/synchro_ftp/BASE/QUOT"

DEPARTEMENTS = (
    [f"{i:02d}" for i in range(1, 96)]
    + ["971", "972", "973", "974", "975"]
    + ["984", "985", "986", "987", "988"]
    + ["99"]
)

# Colonnes gardées et leur nouveau nom
COLONNES = {
    "NUM_POSTE": "NUM_POSTE",
    "AAAAMMJJ": "DATE",
    "NOM_USUEL": "NOM_USUEL",
    "TN": "TMIN",
    "TX": "TMAX",
    "LAT": "LAT",
    "LON": "LON",
    "ALTI": "ALTI",
}


def filtrer_donnees_meteo(chemin_gz: Path) -> pd.DataFrame:
    """Lit un fichier .csv.gz, garde les colonnes utiles et les dates depuis 1990."""
    df = pd.read_csv(
        chemin_gz,
        sep=";",
        encoding="latin1",
        usecols=lambda c: c in COLONNES,
        dtype={"NUM_POSTE": str, "AAAAMMJJ": str},
    )
    df = df.rename(columns=COLONNES)
    return df[df["DATE"] >= "19900101"]


def telecharger_et_traiter(url: str, chemin_tmp: Path) -> pd.DataFrame | None:
    """Télécharge un fichier, le filtre puis supprime le fichier temporaire."""
    response = requests.get(url, timeout=600)
    if response.status_code != 200:
        print(f"   -> fichier absent ({response.status_code}) : {url.rsplit('/', 1)[-1]}")
        return None

    chemin_tmp.write_bytes(response.content)
    try:
        return filtrer_donnees_meteo(chemin_tmp)
    except Exception as e:
        print(f"   -> erreur de lecture : {e}")
        return None
    finally:
        chemin_tmp.unlink(missing_ok=True)


def telecharger_departement(dept: str) -> pd.DataFrame | None:
    """Télécharge et fusionne l'archive (1950-2024) et les données récentes (2025-2026)."""
    fichiers = [
        f"Q_{dept}_previous-1950-2024_RR-T-Vent.csv.gz",
        f"Q_{dept}_latest-2025-2026_RR-T-Vent.csv.gz",
    ]
    morceaux = []
    for nom in fichiers:
        df = telecharger_et_traiter(f"{URL_BASE}/{nom}", DOSSIER_DESTINATION / f"tmp_{nom}")
        if df is not None:
            morceaux.append(df)

    if not morceaux:
        return None
    return pd.concat(morceaux, ignore_index=True).drop_duplicates(subset=["NUM_POSTE", "DATE"])


def collecter_donnees_meteo(departements: list[str]) -> list[pd.DataFrame]:
    """Télécharge les données de chaque département."""
    resultats = []
    for i, dept in enumerate(departements, start=1):
        print(f"[{i}/{len(departements)}] Département {dept}...")
        df = telecharger_departement(dept)
        if df is None:
            print("   -> aucune donnée")
        else:
            resultats.append(df)
            print(f"   -> {len(df):,} lignes")
    return resultats


def consolider_et_exporter(morceaux: list[pd.DataFrame]) -> None:
    """Empile les départements, type les colonnes et écrit le Parquet brut."""
    if not morceaux:
        print("Aucune donnée à exporter.")
        return

    df = pd.concat(morceaux, ignore_index=True)
    df["DATE"] = pd.to_datetime(df["DATE"], format="%Y%m%d")
    for col in ["TMIN", "TMAX", "LAT", "LON", "ALTI"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.sort_values(["NUM_POSTE", "DATE"]).reset_index(drop=True)

    df.to_parquet(FICHIER_BRUT, index=False)
    print(f"Fichier écrit : {FICHIER_BRUT} ({len(df):,} lignes)")


def main() -> None:
    departements = sys.argv[1:] or DEPARTEMENTS
    DOSSIER_DESTINATION.mkdir(exist_ok=True)
    consolider_et_exporter(collecter_donnees_meteo(departements))


if __name__ == "__main__":
    main()
