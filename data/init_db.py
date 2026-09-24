"""Télécharge les données météo Météo-France (1990-2026) et les exporte en Parquet.

Pour chaque département, les deux fichiers sources (archive 1950-2024 et
données récentes 2025-2026) sont téléchargés, filtrés puis fusionnés. Les
résultats de tous les départements sont ensuite empilés, nettoyés et
exportés dans un unique fichier Parquet.
"""

import os

import pandas as pd
import requests

DOSSIER_DESTINATION = "/home/onyxia/work/ensai-it-project-2a-team12/data/raw_data"

DEPARTEMENTS = (
    [f"{i:02d}" for i in range(1, 96)]
    + ["971", "972", "973", "974", "975"]
    + ["984", "985", "986", "987", "988"]
    + ["99"]
)


def filtrer_donnees_meteo(chemin_gz: str) -> pd.DataFrame:
    """Lit un fichier météo compressed .csv.gz, applique les filtres et renomme les colonnes."""
    df = pd.read_csv(
        chemin_gz,
        sep=";",
        low_memory=False,
        encoding="latin1",
        compression="gzip",
    )
    df = df.rename(columns={"AAAAMMJJ": "DATE"})

    colonnes_utiles = [
        "NUM_POSTE",
        "DATE",
        "NOM_USUEL",
        "TN",
        "TX",
        "TM",
        "LAT",
        "LON",
        "ALTI",
        "TNTXM",
    ]
    df = df[[c for c in colonnes_utiles if c in df.columns]]
    df["DATE"] = df["DATE"].astype(str)

    # Conservation des données à partir du 1er janvier 1990
    df = df[df["DATE"] >= "19900101"]

    renommage = {
        "TN": "TMIN",
        "TX": "TMAX",
        "TM": "TMEAN",
        "TNTXM": "TMED_TN_TX",
    }
    return df.rename(columns=renommage)


def telecharger_et_traiter(url: str, chemin_destination: str) -> pd.DataFrame | None:
    """Télécharge un fichier .gz, applique la fonction de nettoyage et le supprime."""
    response = requests.get(url)
    if response.status_code == 200:
        with open(chemin_destination, "wb") as f:
            f.write(response.content)

        try:
            return filtrer_donnees_meteo(chemin_destination)
        except Exception as e:
            print(f"   -> Erreur lors de la lecture du fichier : {e}")
            return None
        finally:
            # Fichier .gz temporaire supprimé après lecture pour ne pas stocker
            # les archives brutes (seul le Parquet final est conservé).
            if os.path.exists(chemin_destination):
                os.remove(chemin_destination)
    else:
        print(f"   -> Fichier non trouvé ou erreur réseau (Code {response.status_code})")
        return None


def telecharger_departement(dept: str) -> pd.DataFrame | None:
    """Télécharge et fusionne les données (1950-2024 et 2025-2026) d'un département."""
    url_1950_2024 = (
        f"https://meteofrance.s3.sbg.io.cloud.ovh.net/data/synchro_ftp/BASE/QUOT/"
        f"Q_{dept}_previous-1950-2024_RR-T-Vent.csv.gz"
    )
    url_2025_2026 = (
        f"https://meteofrance.s3.sbg.io.cloud.ovh.net/data/synchro_ftp/BASE/QUOT/"
        f"Q_{dept}_latest-2025-2026_RR-T-Vent.csv.gz"
    )

    dfs_dept = []

    chemin_tmp_1 = os.path.join(DOSSIER_DESTINATION, f"tmp_{dept}_1950_2024.csv.gz")
    df_old = telecharger_et_traiter(url_1950_2024, chemin_tmp_1)
    if df_old is not None:
        dfs_dept.append(df_old)

    chemin_tmp_2 = os.path.join(DOSSIER_DESTINATION, f"tmp_{dept}_2025_2026.csv.gz")
    df_recent = telecharger_et_traiter(url_2025_2026, chemin_tmp_2)
    if df_recent is not None:
        dfs_dept.append(df_recent)

    if not dfs_dept:
        return None

    # Élimination des doublons sur le poste et la date si recoupement
    return pd.concat(dfs_dept, ignore_index=True).drop_duplicates(subset=["NUM_POSTE", "DATE"])


def collecter_donnees_meteo(departements: list[str]) -> dict[str, pd.DataFrame]:
    """Télécharge et fusionne les données météo de chaque département."""
    dict_meteo_complet: dict[str, pd.DataFrame] = {}

    print("=== DEBUT DU TRAITEMENT METEO (1990 - 2026) ===")

    for dept in departements:
        print(f"\nTraitement du département {dept}...")
        df_dept = telecharger_departement(dept)

        if df_dept is not None:
            dict_meteo_complet[dept] = df_dept
            print(f"   -> OK : {len(df_dept)} lignes conservées pour le dép {dept}.")
        else:
            print(f"   -> AUCUNE DONNEE récupérée pour le département {dept}.")

    print(
        f"\nTraitement terminé avec succès ! "
        f"Dictionnaire prêt avec {len(dict_meteo_complet)} départements."
    )
    return dict_meteo_complet


def consolider_et_exporter(dict_meteo_complet: dict[str, pd.DataFrame]) -> None:
    """Empile les données de tous les départements et les exporte en Parquet."""
    if not dict_meteo_complet:
        print("Aucune donnée disponible pour l'export.")
        return

    print("\n=== CONSOLIDATION ET EXPORT PARQUET ===")

    # 1. Empilage de tous les DataFrames de départements en un seul
    df_global = pd.concat(dict_meteo_complet.values(), ignore_index=True)

    # 2. Nettoyage et typage propre des colonnes
    # Conversion de la date au format datetime (YYYY-MM-DD)
    df_global["DATE"] = pd.to_datetime(df_global["DATE"], format="%Y%m%d")

    # Conversion des colonnes numériques
    cols_float = ["TMIN", "TMAX", "TMEAN", "TMED_TN_TX", "LAT", "LON", "ALTI"]
    for col in cols_float:
        if col in df_global.columns:
            df_global[col] = pd.to_numeric(df_global[col], errors="coerce")

    # Conversion des identifiants/textes en string / category
    df_global["NUM_POSTE"] = df_global["NUM_POSTE"].astype(str)
    if "NOM_USUEL" in df_global.columns:
        df_global["NOM_USUEL"] = df_global["NOM_USUEL"].astype("category")

    # Tri chronologique et par station
    df_global = df_global.sort_values(by=["NUM_POSTE", "DATE"]).reset_index(drop=True)

    # 3. Export en Parquet
    chemin_parquet = os.path.join(DOSSIER_DESTINATION, "meteo_france_1990_2026.parquet")

    # Nécessite pyarrow ou fastparquet (pip install pyarrow)
    df_global.to_parquet(chemin_parquet, index=False, engine="pyarrow", compression="snappy")

    print("Export terminé avec succès !")
    print(f"Fichier généré : {chemin_parquet}")
    print(f"Volume total : {len(df_global):,} lignes / {len(df_global.columns)} colonnes")


def main() -> None:
    os.makedirs(DOSSIER_DESTINATION, exist_ok=True)
    dict_meteo_complet = collecter_donnees_meteo(DEPARTEMENTS)
    consolider_et_exporter(dict_meteo_complet)


if __name__ == "__main__":
    main()
