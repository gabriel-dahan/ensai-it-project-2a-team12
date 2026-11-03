"""Télécharge régions, départements et communes (avec altitude) et écrit les Parquet."""

from pathlib import Path

import pandas as pd
import requests

DOSSIER_DESTINATION = Path(__file__).resolve().parent / "raw_data"
URL_GEO = "https://geo.api.gouv.fr"
URL_ALTI = "https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json"
BATCH_SIZE = 250


def fetch_json(chemin: str) -> list[dict]:
    """Appelle geo.api.gouv.fr et renvoie la réponse JSON."""
    response = requests.get(f"{URL_GEO}{chemin}", timeout=300)
    response.raise_for_status()
    return response.json()


def fetch_regions() -> pd.DataFrame:
    """Régions : code, nom."""
    return pd.DataFrame(fetch_json("/regions?fields=code,nom"))[["code", "nom"]]


def fetch_departements() -> pd.DataFrame:
    """Départements : code, nom, codeRegion."""
    df = pd.DataFrame(fetch_json("/departements?fields=code,nom,codeRegion"))
    return df[["code", "nom", "codeRegion"]]


def fetch_altitudes(lons: list[float], lats: list[float]) -> list[float | None]:
    """Altitudes d'un lot de points via l'API IGN (None si inconnue)."""
    url = (
        f"{URL_ALTI}?lon={'|'.join(map(str, lons))}&lat={'|'.join(map(str, lats))}"
        "&resource=ign_rge_alti_wld&zonly=true"
    )
    try:
        response = requests.get(url, timeout=120)
        response.raise_for_status()
        altitudes = response.json()["elevations"]
    except Exception:
        if len(lons) == 1:
            return [None]
        # Un point hors couverture fait échouer tout le lot : on réessaie point par point
        print(f"   -> erreur sur un lot, nouvel essai point par point ({len(lons)} points)")
        return [fetch_altitudes([lon], [lat])[0] for lon, lat in zip(lons, lats)]
    # L'IGN renvoie -99999 quand il ne connaît pas l'altitude
    return [z if z is not None and z > -1000 else None for z in altitudes]


def _coordonnees(commune: dict) -> list[float]:
    """Coordonnées [lon, lat] de la mairie, ou du centre de la commune si la mairie manque.

    La mairie est plus proche de l'endroit où vivent les habitants que le
    centre géométrique (Chamonix : 1 036 m à la mairie, 1 885 m au centre).
    """
    point = commune.get("mairie") or commune["centre"]
    return point["coordinates"]


def fetch_communes() -> pd.DataFrame:
    """Communes : code, nom, coordonnées, altitude, population, département, région."""
    communes = fetch_json(
        "/communes?fields=code,nom,mairie,centre,population,codeDepartement,codeRegion"
    )
    communes = [c for c in communes if c.get("mairie") or c.get("centre")]
    print(f"{len(communes)} communes, calcul des altitudes...")

    lignes = []
    for i in range(0, len(communes), BATCH_SIZE):
        lot = communes[i : i + BATCH_SIZE]
        lons = [_coordonnees(c)[0] for c in lot]
        lats = [_coordonnees(c)[1] for c in lot]
        altitudes = fetch_altitudes(lons, lats)

        for c, lon, lat, alti in zip(lot, lons, lats, altitudes):
            lignes.append(
                {
                    "code": c["code"],
                    "nom": c["nom"],
                    "latitude": lat,
                    "longitude": lon,
                    "altitude": alti,
                    "population": c.get("population"),
                    "codeDepartement": c.get("codeDepartement"),
                    "codeRegion": c.get("codeRegion"),
                }
            )
        print(f"   {min(i + BATCH_SIZE, len(communes))} / {len(communes)}")

    df = pd.DataFrame(lignes)
    df["population"] = df["population"].astype("Int64")
    return df


def main() -> None:
    DOSSIER_DESTINATION.mkdir(exist_ok=True)
    tables = {
        "regions": fetch_regions(),
        "departements": fetch_departements(),
        "communes": fetch_communes(),
    }
    for nom, df in tables.items():
        chemin = DOSSIER_DESTINATION / f"{nom}.parquet"
        df.to_parquet(chemin, index=False)
        print(f"Fichier écrit : {chemin} ({len(df):,} lignes)")


if __name__ == "__main__":
    main()
