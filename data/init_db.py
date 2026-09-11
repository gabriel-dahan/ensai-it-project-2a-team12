import os
import pandas as pd
import requests

DOSSIER_DESTINATION = (
    "/home/onyxia/work/ensai-it-project-2a-team12/data/raw_data"
)

# 1. Génération dynamique de la liste de tous les départements
DEPARTEMENTS = (
    [f"{i:02d}" for i in range(1, 96)]  # "01" à "95"
    + ["971", "972", "973", "974", "975"]  # DOMs
    + ["984", "985", "986", "987", "988"]  # TOMs / Collectivités
    + ["99"]  
)


def filtrer_donnees_meteo(chemin_gz):
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


def telecharger_et_traiter(url, chemin_destination):
    """Télécharge un fichier .gz, applique la fonction de nettoyage et le supprime."""
    response = requests.get(url)
    if response.status_code == 200:
        with open(chemin_destination, "wb") as f:
            f.write(response.content)

        try:
            df = filtrer_donnees_meteo(chemin_destination)
            return df
        except Exception as e:
            print(f"   -> Erreur lors de la lecture du fichier : {e}")
            return None
        finally:
            if os.path.exists(chemin_destination):
                os.remove(chemin_destination)
    else:
        print(
            f"   -> Fichier non trouvé ou erreur réseau (Code {response.status_code})"
        )
        return None


# ==============================================================================
# SCRIPT PRINCIPAL
# ==============================================================================

os.makedirs(DOSSIER_DESTINATION, exist_ok=True)
dict_meteo_complet = {}

print("=== DEBUT DU TRAITEMENT METEO (1990 - 2026) ===")

for dept in DEPARTEMENTS:
    print(f"\nTraitement du département {dept}...")

    # Modèles d'URL OVH / Météo-France
    url_1950_2024 = f"https://meteofrance.s3.sbg.io.cloud.ovh.net/data/synchro_ftp/BASE/QUOT/Q_{dept}_previous-1950-2024_RR-T-Vent.csv.gz"
    url_2025_2026 = f"https://meteofrance.s3.sbg.io.cloud.ovh.net/data/synchro_ftp/BASE/QUOT/Q_{dept}_latest-2025-2026_RR-T-Vent.csv.gz"

    dfs_dept = []

    # 1. Récupération 1950-2024 (qui sera filtré post-1990 par la fonction)
    chemin_tmp_1 = os.path.join(
        DOSSIER_DESTINATION, f"tmp_{dept}_1950_2024.csv.gz"
    )
    df_old = telecharger_et_traiter(url_1950_2024, chemin_tmp_1)
    if df_old is not None:
        dfs_dept.append(df_old)

    # 2. Récupération 2025-2026
    chemin_tmp_2 = os.path.join(
        DOSSIER_DESTINATION, f"tmp_{dept}_2025_2026.csv.gz"
    )
    df_recent = telecharger_et_traiter(url_2025_2026, chemin_tmp_2)
    if df_recent is not None:
        dfs_dept.append(df_recent)

    # 3. Fusion et nettoyage final du département
    if dfs_dept:
        df_final_dept = pd.concat(dfs_dept, ignore_index=True)
        # Élimination des doublons sur le poste et la date si recoupement
        df_final_dept = df_final_dept.drop_duplicates(
            subset=["NUM_POSTE", "DATE"]
        )

        dict_meteo_complet[dept] = df_final_dept
        print(
            f"   -> OK : {len(df_final_dept)} lignes conservées pour le dép {dept}."
        )
    else:
        print(
            f"   -> AUCUNE DONNEE récupérée pour le département {dept}."
        )

print(
    f"\nTraitement terminé avec succès ! Dictionnaire prêt avec {len(dict_meteo_complet)} départements."
)

# ==============================================================================
# COMBINAISON ET EXPORT EN PARQUET
# ==============================================================================

if dict_meteo_complet:
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

    print(f"Export terminé avec succès !")
    print(f"Fichier généré : {chemin_parquet}")
    print(f"Volume total : {len(df_global):,} lignes / {len(df_global.columns)} colonnes")

else:
    print("Aucune donnée disponible pour l'export.")