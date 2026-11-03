"""Comble les valeurs manquantes de TMIN et TMAX et écrit le Parquet nettoyé.

Paliers selon la longueur du trou :
    - 1 à 2 jours : interpolation linéaire ;
    - 3 à 7 jours : 70 % tendance locale + 30 % moyenne des stations voisines ;
    - 8 à 30 jours : régression linéaire sur les stations voisines ;
    - plus de 30 jours : pas de comblement.
La colonne SOURCE_TMIN / SOURCE_TMAX indique l'origine de chaque valeur.
"""

from pathlib import Path

import numpy as np
import pandas as pd

DOSSIER = Path(__file__).resolve().parent / "raw_data"
FICHIER_BRUT = DOSSIER / "meteo_france_brut.parquet"
FICHIER_NETTOYE = DOSSIER / "meteo_france_nettoye.parquet"

COLONNES_A_COMBLER = ["TMIN", "TMAX"]
COLONNES_METADONNEES_STATION = ["NUM_POSTE", "NOM_USUEL", "LAT", "LON", "ALTI"]

LIMITE_GAP_COURT = 2  # jours
LIMITE_GAP_MOYEN = 7  # jours
LIMITE_GAP_LONG = 30  # jours, au-delà : rejeté

NB_STATIONS_VOISINES = 5
SEUIL_JOURS_AJUSTEMENT_REGRESSION = 30  # jours communs minimum pour la régression


def _longueur_trou(masque_manquant: pd.Series) -> pd.Series:
    """Longueur du trou auquel appartient chaque jour manquant (NaN sinon)."""
    groupes = (masque_manquant != masque_manquant.shift()).cumsum()
    longueurs = masque_manquant.groupby(groupes).transform("sum")
    return longueurs.where(masque_manquant)


def _tendance_locale(serie: pd.Series) -> pd.Series:
    """Interpolation linéaire à l'intérieur de la série (pas d'extrapolation)."""
    return serie.interpolate(method="linear", limit_area="inside")


def _grille_journaliere(df_station: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par jour entre la première et la dernière observation d'une station."""
    df_station = df_station.sort_values("DATE")
    calendrier = pd.date_range(
        df_station["DATE"].min(), df_station["DATE"].max(), freq="D", name="DATE"
    )
    grille = df_station.set_index("DATE").reindex(calendrier).reset_index()

    # Les jours ajoutés reprennent les métadonnées de la station
    for colonne in COLONNES_METADONNEES_STATION:
        grille[colonne] = grille[colonne].ffill().bfill()
    return grille


def _initialiser_suivi(grille: pd.DataFrame) -> pd.DataFrame:
    """Ajoute LONGUEUR_TROU_* et SOURCE_* ("observee" ou "manquante")."""
    grille = grille.copy()
    for colonne in COLONNES_A_COMBLER:
        manquant = grille[colonne].isna()
        grille[f"LONGUEUR_TROU_{colonne}"] = _longueur_trou(manquant)
        grille[f"SOURCE_{colonne}"] = "observee"
        grille.loc[manquant, f"SOURCE_{colonne}"] = "manquante"
    return grille


def _combler_gaps_courts(grille: pd.DataFrame) -> pd.DataFrame:
    """Trous de 1 à 2 jours : interpolation linéaire."""
    grille = grille.copy()
    for colonne in COLONNES_A_COMBLER:
        eligible = grille[f"LONGUEUR_TROU_{colonne}"].between(1, LIMITE_GAP_COURT)
        candidat = _tendance_locale(grille[colonne])

        a_remplir = eligible & grille[colonne].isna() & candidat.notna()
        grille.loc[a_remplir, colonne] = candidat[a_remplir]
        grille.loc[a_remplir, f"SOURCE_{colonne}"] = "interpolee_1_2j"
    return grille


def _distance_km(lat1, lon1, lat2, lon2):
    """Distance à vol d'oiseau en km (formule de Haversine)."""
    rayon_terre_km = 6371.0
    lat1, lon1, lat2, lon2 = np.radians(lat1), np.radians(lon1), np.radians(lat2), np.radians(lon2)
    a = (
        np.sin((lat2 - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * rayon_terre_km * np.arcsin(np.sqrt(a))


def _calculer_voisinage(grille: pd.DataFrame, n: int) -> dict[str, list[str]]:
    """Les n stations les plus proches de chaque station."""
    stations = grille.drop_duplicates("NUM_POSTE")[["NUM_POSTE", "LAT", "LON"]]
    voisinage = {}
    for _, station in stations.iterrows():
        autres = stations[stations["NUM_POSTE"] != station["NUM_POSTE"]].copy()
        autres["DISTANCE_KM"] = _distance_km(
            station["LAT"], station["LON"], autres["LAT"], autres["LON"]
        )
        voisinage[station["NUM_POSTE"]] = autres.nsmallest(n, "DISTANCE_KM")["NUM_POSTE"].tolist()
    return voisinage


def _pivoter_observations_reelles(grille: pd.DataFrame, colonne: str) -> pd.DataFrame:
    """Table DATE x NUM_POSTE des seules mesures observées."""
    reelles = grille[grille[f"SOURCE_{colonne}"] == "observee"]
    return reelles.pivot(index="DATE", columns="NUM_POSTE", values=colonne)


def _combler_gaps_moyens(
    grille: pd.DataFrame, pivots: dict[str, pd.DataFrame], voisines: list[str]
) -> pd.DataFrame:
    """Trous de 3 à 7 jours : 70 % tendance locale + 30 % moyenne des voisines."""
    grille = grille.copy()
    for colonne in COLONNES_A_COMBLER:
        eligible = grille[f"LONGUEUR_TROU_{colonne}"].between(
            LIMITE_GAP_COURT + 1, LIMITE_GAP_MOYEN
        )
        if not eligible.any():
            continue

        tendance_locale = _tendance_locale(grille[colonne])

        voisines_disponibles = [v for v in voisines if v in pivots[colonne].columns]
        if voisines_disponibles:
            moyenne_voisines = (
                pivots[colonne]
                .reindex(grille["DATE"])[voisines_disponibles]
                .mean(axis=1)
                .set_axis(grille.index)
            )
        else:
            moyenne_voisines = pd.Series(index=grille.index, dtype=float)

        candidat = 0.7 * tendance_locale + 0.3 * moyenne_voisines

        a_remplir = eligible & grille[colonne].isna() & candidat.notna()
        grille.loc[a_remplir, colonne] = candidat[a_remplir]
        grille.loc[a_remplir, f"SOURCE_{colonne}"] = "interpolee_3_7j"
    return grille


def _regression_multi_station(
    grille: pd.DataFrame, colonne: str, pivot: pd.DataFrame, voisines: list[str]
) -> pd.Series:
    """Estime T_cible = a1*T_v1 + ... + ak*T_vk + b à partir des voisines (NaN si impossible)."""
    voisines_disponibles = [v for v in voisines if v in pivot.columns]
    if len(voisines_disponibles) < 2:
        return pd.Series(index=grille.index, dtype=float)

    voisines_alignees = pivot.reindex(grille["DATE"])[voisines_disponibles].set_axis(grille.index)
    cible = grille[colonne]

    # Ajustement sur les jours où la cible et toutes les voisines sont observées
    periode_ajustement = cible.notna() & voisines_alignees.notna().all(axis=1)
    if periode_ajustement.sum() < SEUIL_JOURS_AJUSTEMENT_REGRESSION:
        return pd.Series(index=grille.index, dtype=float)

    x_ajustement = np.column_stack(
        [voisines_alignees.loc[periode_ajustement].to_numpy(), np.ones(periode_ajustement.sum())]
    )
    y_ajustement = cible.loc[periode_ajustement].to_numpy()
    coefficients, *_ = np.linalg.lstsq(x_ajustement, y_ajustement, rcond=None)

    periode_estimable = voisines_alignees.notna().all(axis=1)
    x_tout = np.column_stack([voisines_alignees.to_numpy(), np.ones(len(voisines_alignees))])
    estimation = pd.Series(x_tout @ coefficients, index=grille.index)
    return estimation.where(periode_estimable)


def _combler_gaps_longs(
    grille: pd.DataFrame, pivots: dict[str, pd.DataFrame], voisines: list[str]
) -> pd.DataFrame:
    """Trous de 8 à 30 jours : régression sur les stations voisines."""
    grille = grille.copy()
    for colonne in COLONNES_A_COMBLER:
        eligible = grille[f"LONGUEUR_TROU_{colonne}"].between(LIMITE_GAP_MOYEN + 1, LIMITE_GAP_LONG)
        if not eligible.any():
            continue

        candidat = _regression_multi_station(grille, colonne, pivots[colonne], voisines)

        a_remplir = eligible & grille[colonne].isna() & candidat.notna()
        grille.loc[a_remplir, colonne] = candidat[a_remplir]
        grille.loc[a_remplir, f"SOURCE_{colonne}"] = "estimee_7_30j"
    return grille


def _marquer_gaps_rejetes(grille: pd.DataFrame) -> pd.DataFrame:
    """Trous de plus de 30 jours : source "rejetee_gap_trop_long"."""
    grille = grille.copy()
    for colonne in COLONNES_A_COMBLER:
        trop_long = grille[colonne].isna() & (grille[f"LONGUEUR_TROU_{colonne}"] > LIMITE_GAP_LONG)
        grille.loc[trop_long, f"SOURCE_{colonne}"] = "rejetee_gap_trop_long"
    return grille


def traiter_valeurs_manquantes(df: pd.DataFrame) -> pd.DataFrame:
    """Comble TMIN et TMAX sur un calendrier journalier complet par station."""
    grille = pd.concat(
        (_initialiser_suivi(_grille_journaliere(s)) for _, s in df.groupby("NUM_POSTE")),
        ignore_index=True,
    )
    grille = pd.concat(
        (_combler_gaps_courts(s) for _, s in grille.groupby("NUM_POSTE")), ignore_index=True
    )

    voisinage = _calculer_voisinage(grille, NB_STATIONS_VOISINES)
    pivots = {c: _pivoter_observations_reelles(grille, c) for c in COLONNES_A_COMBLER}

    grille = pd.concat(
        (_combler_gaps_moyens(s, pivots, voisinage[p]) for p, s in grille.groupby("NUM_POSTE")),
        ignore_index=True,
    )
    grille = pd.concat(
        (_combler_gaps_longs(s, pivots, voisinage[p]) for p, s in grille.groupby("NUM_POSTE")),
        ignore_index=True,
    )
    return _marquer_gaps_rejetes(grille)


def main() -> None:
    df_brut = pd.read_parquet(FICHIER_BRUT)
    # Les stations sans aucune température (pluviomètres) sont inutiles
    df_brut = df_brut[df_brut["TMIN"].notna() | df_brut["TMAX"].notna()]
    print(f"{len(df_brut):,} lignes avec température, {df_brut['NUM_POSTE'].nunique()} stations")

    df = traiter_valeurs_manquantes(df_brut)
    df = df[df["TMIN"].notna() | df["TMAX"].notna()]
    df = df.drop(columns=[f"LONGUEUR_TROU_{c}" for c in COLONNES_A_COMBLER])

    print("SOURCE_TMIN :\n", df["SOURCE_TMIN"].value_counts())
    print("SOURCE_TMAX :\n", df["SOURCE_TMAX"].value_counts())

    df.to_parquet(FICHIER_NETTOYE, index=False)
    print(f"Fichier écrit : {FICHIER_NETTOYE} ({len(df):,} lignes)")


if __name__ == "__main__":
    main()
