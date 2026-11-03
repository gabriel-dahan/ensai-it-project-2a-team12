"""Affiche un résumé (taille, colonnes, aperçu) des fichiers Parquet de raw_data."""

from pathlib import Path

import pandas as pd

DOSSIER = Path(__file__).resolve().parent / "raw_data"


def resumer_parquet(chemin: Path, nb_lignes: int = 5) -> None:
    """Affiche le nombre de lignes, les types des colonnes et les premières lignes."""
    df = pd.read_parquet(chemin)
    print(f"\n=== {chemin.name} : {len(df):,} lignes ===")
    print(df.dtypes.to_string())
    print(df.head(nb_lignes).to_string())


if __name__ == "__main__":
    for chemin in sorted(DOSSIER.glob("*.parquet")):
        resumer_parquet(chemin)

    # Exemple : les 5 stations les plus hautes
    chemin_meteo = DOSSIER / "meteo_france_nettoye.parquet"
    if chemin_meteo.exists():
        stations = pd.read_parquet(chemin_meteo, columns=["NUM_POSTE", "NOM_USUEL", "ALTI"])
        print("\n=== Stations les plus hautes ===")
        print(stations.drop_duplicates("NUM_POSTE").nlargest(5, "ALTI").to_string(index=False))
