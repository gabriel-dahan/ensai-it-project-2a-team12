"""Fetch French municipalities from open data APIs."""

from __future__ import annotations
import os
from pathlib import Path

import pandas as pd
import requests

URL_GEO = (
    "https://geo.api.gouv.fr/communes"
    "?fields=code,nom,population,codesPostaux,mairie,centre,departement,region&format=json"
)
URL_ALTI = "https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json"
# Sans ce paramètre, l'API d'altimétrie répond 405 et aucune altitude n'est récupérée
RESSOURCE_ALTI = "ign_rge_alti_wld"
# Valeur renvoyée par l'API quand elle n'a pas d'altitude (point en mer par exemple)
ALTITUDE_INCONNUE = -99999
BATCH_SIZE = 250
DOSSIER_DESTINATION = Path(__file__).resolve().parent / "raw_data"

def _coordonnees(commune: dict) -> list[float]:
    """Coordonnées [lon, lat] de la mairie, ou du centre de la commune si la mairie manque.

    La mairie est plus proche de l'endroit où vivent les habitants que le
    centre géométrique (Chamonix : 1 036 m à la mairie, 1 885 m au centre).
    """
    point = commune.get("mairie") or commune["centre"]
    return point["coordinates"]


def fetch_communes() -> list[dict]:
    """Download communes and enrich them with altitude.

    Returns:
        List of dicts with keys: Code_Insee, Commune, Population, Code_Postal,
        Dept, Nom_Dept, Region, Nom_Region, Lon, Lat, Altitude.
    """
    communes = [
        c for c in requests.get(URL_GEO, timeout=120).json() if "mairie" in c or "centre" in c
    ]
    donnees: list[dict] = []

    print(f"Début du traitement de {len(communes)} communes...")

    for i in range(0, len(communes), BATCH_SIZE):
        lot = communes[i : i + BATCH_SIZE]
        lons = "|".join(str(_coordonnees(c)[0]) for c in lot)
        lats = "|".join(str(_coordonnees(c)[1]) for c in lot)
        url_get = f"{URL_ALTI}?lon={lons}&lat={lats}&resource={RESSOURCE_ALTI}"

        try:
            response = requests.get(url_get, timeout=120)
            if response.status_code == 200:
                altis = response.json().get("elevations", [])
            else:
                print(f"Erreur API sur le lot {i}: {response.status_code}")
                altis = []
        except Exception as e:
            print(f"Erreur réseau sur le lot {i}: {e}")
            altis = []

        for j, c in enumerate(lot):
            liste_cp = c.get("codesPostaux", [])
            code_postal = liste_cp[0] if liste_cp else ""
            altitude = altis[j].get("z") if j < len(altis) else None
            if altitude == ALTITUDE_INCONNUE:
                altitude = None

            donnees.append(
                {
                    "Code_Insee": c.get("code"),
                    "Commune": c.get("nom"),
                    "Population": c.get("population"),
                    "Code_Postal": code_postal,
                    "Dept": c.get("departement", {}).get("code"),
                    "Nom_Dept": c.get("departement", {}).get("nom"),
                    "Region": c.get("region", {}).get("code"),
                    "Nom_Region": c.get("region", {}).get("nom"),
                    "Lon": _coordonnees(c)[0],
                    "Lat": _coordonnees(c)[1],
                    "Altitude": altitude,
                }
            )

        print(f"Progression : {min(i + BATCH_SIZE, len(communes))} / {len(communes)}")

    return donnees


if __name__ == "__main__":
    rows = fetch_communes()
    print("Création du fichier Parquet...")
    df = pd.DataFrame(rows)

    df["Code_Postal"] = df["Code_Postal"].astype(str)
    df["Dept"] = df["Dept"].astype(str)
    df["Region"] = df["Region"].astype(str) 
    # Export Parquet
    os.makedirs(DOSSIER_DESTINATION, exist_ok=True)
    chemin_parquet= os.path.join(DOSSIER_DESTINATION, "communes.parquet")
    df.to_parquet(chemin_parquet,
        index=False,
        engine="pyarrow",
        compression="snappy"
    )
    print("Fichier communes.parquet généré avec succès !")