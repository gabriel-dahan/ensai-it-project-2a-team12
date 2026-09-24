"""Traitement des valeurs manquantes dans les séries météo journalières.

Entrée : DataFrame consolidé produit par `init_db.py` (une ligne par station
et par jour : NUM_POSTE, DATE, TMIN, TMAX, TMEAN, TMED_TN_TX, ...).

Les jours manquants prennent deux formes : absence de ligne (rattrapée par
un reindex sur le calendrier complet) ou ligne à valeurs vides (`NaN`).
Les deux sont ensuite traités de la même façon.

Seuls TMIN et TMAX sont comblés, car ils servent au calcul du DJU.
TMED_TN_TX est déduite de (TMIN + TMAX) / 2 ; TMEAN n'est pas traitée.

Méthode de comblement, par paliers selon la longueur du trou :
    - 1 à 2 jours : interpolation linéaire ;
    - 3 à 7 jours : 70 % tendance locale + 30 % moyenne des stations voisines ;
    - 8 à 30 jours : régression linéaire sur les stations voisines ;
    - au-delà de 30 jours : aucun comblement.

Chaque valeur est accompagnée d'une colonne SOURCE_* indiquant son origine.
"""
from pathlib import Path

import numpy as np
import pandas as pd

COLONNES_A_COMBLER = ["TMIN", "TMAX"]
COLONNES_METADONNEES_STATION = ["NUM_POSTE", "NOM_USUEL", "LAT", "LON", "ALTI"]

LIMITE_GAP_COURT = 2  # jours
LIMITE_GAP_MOYEN = 7  # jours
LIMITE_GAP_LONG = 30  # jours, au-delà : rejeté

NB_STATIONS_VOISINES = 5
SEUIL_JOURS_AJUSTEMENT_REGRESSION = 30  # jours communs mini pour fiabiliser la régression


def _longueur_trou(masque_manquant: pd.Series) -> pd.Series:
    """Calcule la longueur du trou consécutif auquel appartient chaque valeur manquante.

    Args:
        masque_manquant: Masque booléen, True pour un jour manquant.

    Returns:
        Série de la longueur du trou pour chaque jour manquant (ex : 5 pour
        chaque jour d'un trou de 5 jours), NaN pour les jours renseignés.
    """
    groupes = (masque_manquant != masque_manquant.shift()).cumsum()
    longueurs = masque_manquant.groupby(groupes).transform("sum")
    return longueurs.where(masque_manquant)


def _tendance_locale(serie: pd.Series) -> pd.Series:
    """Interpole linéairement chaque trou entre les valeurs connues qui l'encadrent.

    Pas d'extrapolation : un trou en début ou fin de série reste manquant.

    Args:
        serie: Série de températures d'une station.

    Returns:
        Série interpolée, NaN là où aucune valeur connue n'encadre le trou.
    """
    return serie.interpolate(method="linear", limit_area="inside")


def _grille_journaliere(df_station: pd.DataFrame) -> pd.DataFrame:
    """Réindexe une station sur un calendrier journalier complet.

    Args:
        df_station: Observations d'une seule station.

    Returns:
        DataFrame avec une ligne par jour entre la première et la dernière
        observation ; les jours ajoutés héritent des métadonnées de la station.
    """
    df_station = df_station.sort_values("DATE")
    calendrier = pd.date_range(
        df_station["DATE"].min(), df_station["DATE"].max(), freq="D", name="DATE"
    )
    grille = df_station.set_index("DATE").reindex(calendrier).reset_index()

    # Métadonnées constantes dans le temps : propagées aux jours ajoutés.
    for colonne in COLONNES_METADONNEES_STATION:
        if colonne in grille.columns:
            grille[colonne] = grille[colonne].ffill().bfill()

    return grille


def _initialiser_suivi(grille: pd.DataFrame) -> pd.DataFrame:
    """Ajoute les colonnes de suivi LONGUEUR_TROU_* et SOURCE_* pour TMIN et TMAX.

    La longueur du trou est calculée une seule fois, avant tout comblement,
    pour que chaque palier s'appuie sur la longueur d'origine.

    Args:
        grille: Grille journalière d'une station.

    Returns:
        Copie de la grille avec SOURCE_* valant "observee" ou "manquante".
    """
    grille = grille.copy()
    for colonne in COLONNES_A_COMBLER:
        manquant = grille[colonne].isna()
        grille[f"LONGUEUR_TROU_{colonne}"] = _longueur_trou(manquant)
        grille[f"SOURCE_{colonne}"] = "observee"
        grille.loc[manquant, f"SOURCE_{colonne}"] = "manquante"
    return grille


def _combler_gaps_courts(grille: pd.DataFrame) -> pd.DataFrame:
    """Comble les trous de 1 à 2 jours par interpolation linéaire.

    Args:
        grille: Grille journalière d'une station.

    Returns:
        Copie de la grille avec les valeurs comblées, source "interpolee_1_2j".
    """
    grille = grille.copy()
    for colonne in COLONNES_A_COMBLER:
        eligible = grille[f"LONGUEUR_TROU_{colonne}"].between(1, LIMITE_GAP_COURT)
        candidat = _tendance_locale(grille[colonne])

        a_remplir = eligible & grille[colonne].isna() & candidat.notna()
        grille.loc[a_remplir, colonne] = candidat[a_remplir]
        grille.loc[a_remplir, f"SOURCE_{colonne}"] = "interpolee_1_2j"
    return grille


def _metadonnees_stations(grille: pd.DataFrame) -> pd.DataFrame:
    """Extrait les coordonnées de chaque station.

    Args:
        grille: Grille journalière de toutes les stations.

    Returns:
        DataFrame d'une ligne par station : NUM_POSTE, LAT, LON.
    """
    return grille.drop_duplicates("NUM_POSTE")[["NUM_POSTE", "LAT", "LON"]].reset_index(drop=True)


def _distance_km(lat1, lon1, lat2, lon2):
    """Calcule la distance à vol d'oiseau (formule de Haversine).

    Args:
        lat1: Latitude du point de départ, en degrés.
        lon1: Longitude du point de départ, en degrés.
        lat2: Latitude du ou des points d'arrivée, en degrés.
        lon2: Longitude du ou des points d'arrivée, en degrés.

    Returns:
        Distance en kilomètres (scalaire ou tableau selon les entrées).
    """
    rayon_terre_km = 6371.0
    lat1, lon1, lat2, lon2 = np.radians(lat1), np.radians(lon1), np.radians(lat2), np.radians(lon2)
    a = (
        np.sin((lat2 - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * rayon_terre_km * np.arcsin(np.sqrt(a))


def _calculer_voisinage(grille: pd.DataFrame, n: int) -> dict[str, list[str]]:
    """Détermine les `n` stations les plus proches de chaque station.

    Args:
        grille: Grille journalière de toutes les stations.
        n: Nombre de voisines à retenir.

    Returns:
        Dictionnaire {NUM_POSTE: liste des NUM_POSTE voisins, du plus proche
        au plus éloigné}.
    """
    stations = _metadonnees_stations(grille)
    voisinage = {}
    for _, station in stations.iterrows():
        autres = stations[stations["NUM_POSTE"] != station["NUM_POSTE"]].copy()
        autres["DISTANCE_KM"] = _distance_km(
            station["LAT"], station["LON"], autres["LAT"], autres["LON"]
        )
        voisinage[station["NUM_POSTE"]] = autres.nsmallest(n, "DISTANCE_KM")["NUM_POSTE"].tolist()
    return voisinage


def _pivoter_observations_reelles(grille: pd.DataFrame, colonne: str) -> pd.DataFrame:
    """Construit la table DATE x NUM_POSTE des mesures réellement observées.

    Les valeurs déjà comblées sont exclues : seules des mesures réelles
    servent à estimer les stations voisines.

    Args:
        grille: Grille journalière de toutes les stations.
        colonne: Colonne de température à pivoter ("TMIN" ou "TMAX").

    Returns:
        DataFrame indexé par DATE, une colonne par station.
    """
    reelles = grille[grille[f"SOURCE_{colonne}"] == "observee"]
    return reelles.pivot(index="DATE", columns="NUM_POSTE", values=colonne)


def _combler_gaps_moyens(
    grille: pd.DataFrame, pivots: dict[str, pd.DataFrame], voisines: list[str]
) -> pd.DataFrame:
    """Comble les trous de 3 à 7 jours : 70 % tendance locale + 30 % moyenne des voisines.

    Un trou en début ou fin d'historique n'est pas comblé (pas de tendance locale).

    Args:
        grille: Grille journalière d'une station.
        pivots: Observations réelles DATE x NUM_POSTE, par colonne.
        voisines: NUM_POSTE des stations voisines.

    Returns:
        Copie de la grille avec les valeurs comblées, source "interpolee_3_7j".
    """
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
    """Estime la température d'une station par régression sur ses voisines.

    Modèle : T_cible = a1*T_v1 + ... + ak*T_vk + b, ajusté sur les jours où
    la cible et toutes les voisines ont une observation réelle.

    Args:
        grille: Grille journalière de la station cible.
        colonne: Colonne de température à estimer ("TMIN" ou "TMAX").
        pivot: Observations réelles DATE x NUM_POSTE pour cette colonne.
        voisines: NUM_POSTE des stations voisines.

    Returns:
        Série des valeurs estimées, entièrement NaN s'il y a moins de 2
        voisines exploitables ou trop peu de jours communs.
    """
    voisines_disponibles = [v for v in voisines if v in pivot.columns]
    if len(voisines_disponibles) < 2:
        return pd.Series(index=grille.index, dtype=float)

    voisines_alignees = pivot.reindex(grille["DATE"])[voisines_disponibles].set_axis(grille.index)
    cible = grille[colonne]

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
    """Comble les trous de 8 à 30 jours par régression multi-station.

    Args:
        grille: Grille journalière d'une station.
        pivots: Observations réelles DATE x NUM_POSTE, par colonne.
        voisines: NUM_POSTE des stations voisines.

    Returns:
        Copie de la grille avec les valeurs comblées, source "estimee_7_30j".
    """
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
    """Marque les trous de plus de 30 jours, qui ne sont jamais comblés.

    Args:
        grille: Grille journalière d'une station.

    Returns:
        Copie de la grille avec la source "rejetee_gap_trop_long" sur ces trous.
    """
    grille = grille.copy()
    for colonne in COLONNES_A_COMBLER:
        trop_long = grille[colonne].isna() & (grille[f"LONGUEUR_TROU_{colonne}"] > LIMITE_GAP_LONG)
        grille.loc[trop_long, f"SOURCE_{colonne}"] = "rejetee_gap_trop_long"
    return grille


def _deduire_tmed_tn_tx(grille: pd.DataFrame) -> pd.DataFrame:
    """Déduit TMED_TN_TX = (TMIN + TMAX) / 2 lorsqu'elle est manquante.

    Les valeurs observées ne sont jamais écrasées.

    Args:
        grille: Grille journalière avec TMIN et TMAX déjà comblées.

    Returns:
        Copie de la grille avec TMED_TN_TX_SOURCE valant "observee",
        "deduite" ou "manquante".
    """
    grille = grille.copy()
    manquante = grille["TMED_TN_TX"].isna()
    deductible = manquante & grille["TMIN"].notna() & grille["TMAX"].notna()

    grille.loc[deductible, "TMED_TN_TX"] = (
        grille.loc[deductible, "TMIN"] + grille.loc[deductible, "TMAX"]
    ) / 2

    grille["TMED_TN_TX_SOURCE"] = "observee"
    grille.loc[manquante, "TMED_TN_TX_SOURCE"] = "manquante"
    grille.loc[deductible, "TMED_TN_TX_SOURCE"] = "deduite"
    return grille


def traiter_valeurs_manquantes(df: pd.DataFrame) -> pd.DataFrame:
    """Comble les valeurs manquantes de TMIN et TMAX, puis déduit TMED_TN_TX.

    Args:
        df: DataFrame consolidé, une ligne par station et par jour.

    Returns:
        DataFrame sur calendrier journalier complet, avec les colonnes de
        suivi LONGUEUR_TROU_*, SOURCE_* et TMED_TN_TX_SOURCE.
    """
    grille = pd.concat(
        (_initialiser_suivi(_grille_journaliere(s)) for _, s in df.groupby("NUM_POSTE")),
        ignore_index=True,
    )

    grille = pd.concat(
        (_combler_gaps_courts(s) for _, s in grille.groupby("NUM_POSTE")), ignore_index=True
    )

    voisinage = _calculer_voisinage(grille, NB_STATIONS_VOISINES)
    pivots = {
        colonne: _pivoter_observations_reelles(grille, colonne) for colonne in COLONNES_A_COMBLER
    }

    grille = pd.concat(
        (
            _combler_gaps_moyens(s, pivots, voisinage[num_poste])
            for num_poste, s in grille.groupby("NUM_POSTE")
        ),
        ignore_index=True,
    )

    grille = pd.concat(
        (
            _combler_gaps_longs(s, pivots, voisinage[num_poste])
            for num_poste, s in grille.groupby("NUM_POSTE")
        ),
        ignore_index=True,
    )

    grille = _marquer_gaps_rejetes(grille)
    return _deduire_tmed_tn_tx(grille)


if __name__ == "__main__":
    chemin_parquet = Path(__file__).resolve().parent / "raw_data" / "meteo_france_1990_2026.parquet"
    df_brut = pd.read_parquet(chemin_parquet)

    df_traite = traiter_valeurs_manquantes(df_brut)

    print("TMIN:\n", df_traite["SOURCE_TMIN"].value_counts())
    print("TMAX:\n", df_traite["SOURCE_TMAX"].value_counts())
    print("TMED_TN_TX:\n", df_traite["TMED_TN_TX_SOURCE"].value_counts())
