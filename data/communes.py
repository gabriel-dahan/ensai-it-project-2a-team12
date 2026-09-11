"""Fetch French municipalities from open data APIs."""

from __future__ import annotations

import pandas as pd
import requests

URL_GEO = (
    "https://geo.api.gouv.fr/communes"
    "?fields=nom,codesPostaux,centre,departement,region&format=json"
)
URL_ALTI = "https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json"
BATCH_SIZE = 250


def fetch_communes() -> list[dict]:
    """Download communes and enrich them with altitude.

    Returns:
        List of dicts with keys: Commune, Code_Postal, Dept, Region,
        Lon, Lat, Altitude.
    """
    communes = [c for c in requests.get(URL_GEO, timeout=120).json() if "centre" in c]
    donnees: list[dict] = []

    print(f"Début du traitement de {len(communes)} communes...")

    for i in range(0, len(communes), BATCH_SIZE):
        lot = communes[i : i + BATCH_SIZE]
        lons = "|".join(str(c["centre"]["coordinates"][0]) for c in lot)
        lats = "|".join(str(c["centre"]["coordinates"][1]) for c in lot)
        url_get = f"{URL_ALTI}?lon={lons}&lat={lats}"

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

            donnees.append(
                {
                    "Commune": c.get("nom"),
                    "Code_Postal": code_postal,
                    "Dept": c.get("departement", {}).get("code"),
                    "Region": c.get("region", {}).get("code"),
                    "Lon": c["centre"]["coordinates"][0],
                    "Lat": c["centre"]["coordinates"][1],
                    "Altitude": altitude,
                }
            )

        print(f"Progression : {min(i + BATCH_SIZE, len(communes))} / {len(communes)}")

    return donnees


if __name__ == "__main__":
    rows = fetch_communes()
    print("Création du fichier CSV...")
    df = pd.DataFrame(rows)
    df.to_csv("communes.csv", index=False, sep=";", encoding="utf-8-sig")
    print("Fichier communes.csv généré avec succès !")
