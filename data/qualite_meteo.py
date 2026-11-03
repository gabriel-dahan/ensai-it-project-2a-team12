"""Traitement des valeurs manquantes dans les séries météo journalières.

Entrée : DataFrame consolidé produit par `meteo.py` (une ligne par station
et par jour : NUM_POSTE, DATE, TMIN, TMAX, ...).

Les lignes sans TMIN ni TMAX sont d'abord retirées : les fichiers Météo-France
contiennent aussi des stations qui ne mesurent que la pluie.

Les jours manquants prennent deux formes : absence de ligne (rattrapée par
un reindex sur le calendrier complet) ou ligne à valeurs vides (`NaN`).
Les deux sont ensuite traités de la même façon.

Seuls TMIN et TMAX sont comblés, car ils servent au calcul du DJU.

Méthode de comblement, par paliers selon la longueur du trou :
    - 1 à 2 jours : interpolation linéaire ;
    - 3 à 7 jours : 70 % tendance locale + 30 % moyenne des stations voisines,
      corrigées de leur écart moyen avec la station ;
    - 8 à 30 jours : régression linéaire sur les stations voisines qui ont
      des mesures pendant tout le trou ;
    - au-delà de 30 jours : aucun comblement.

Les voisines sont les 5 stations les plus proches, dans la France entière,
mais à moins de 50 km : une station isolée a donc moins de voisines, voire aucune.

Enfin, une valeur comblée qui donne TMIN > TMAX est retirée.

Chaque valeur est accompagnée d'une colonne SOURCE_* indiquant son origine.
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
DISTANCE_MAX_VOISINES_KM = 50
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
    """Détermine les `n` stations les plus proches de chaque station, à moins de 50 km.

    Args:
        grille: Grille journalière de toutes les stations.
        n: Nombre maximal de voisines à retenir.

    Returns:
        Dictionnaire {NUM_POSTE: liste des NUM_POSTE voisins, du plus proche
        au plus éloigné}. La liste peut contenir moins de `n` stations.
    """
    stations = _metadonnees_stations(grille)
    voisinage = {}
    for _, station in stations.iterrows():
        autres = stations[stations["NUM_POSTE"] != station["NUM_POSTE"]].copy()
        autres["DISTANCE_KM"] = _distance_km(
            station["LAT"], station["LON"], autres["LAT"], autres["LON"]
        )
        proches = autres[autres["DISTANCE_KM"] <= DISTANCE_MAX_VOISINES_KM]
        voisinage[station["NUM_POSTE"]] = proches.nsmallest(n, "DISTANCE_KM")["NUM_POSTE"].tolist()
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

    Chaque voisine est d'abord ramenée au niveau de la station : on lui ajoute
    l'écart moyen entre les deux stations (dû à l'altitude, à la côte...),
    mesuré sur les jours où elles ont toutes les deux une mesure réelle.
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

        cible = grille[colonne].where(grille[f"SOURCE_{colonne}"] == "observee")
        voisines_alignees = (
            pivots[colonne].reindex(index=grille["DATE"], columns=voisines).set_axis(grille.index)
        )
        # Une voisine sans aucun jour commun avec la station a un écart NaN et est ignorée
        ecarts = pd.Series({v: (cible - voisines_alignees[v]).mean() for v in voisines})
        moyenne_voisines = (voisines_alignees + ecarts).mean(axis=1)

        candidat = 0.7 * tendance_locale + 0.3 * moyenne_voisines

        a_remplir = eligible & grille[colonne].isna() & candidat.notna()
        grille.loc[a_remplir, colonne] = candidat[a_remplir]
        grille.loc[a_remplir, f"SOURCE_{colonne}"] = "interpolee_3_7j"
    return grille


def _regression_sur_trou(
    cible: pd.Series, voisines_alignees: pd.DataFrame, jours_trou: pd.Index
) -> pd.Series | None:
    """Estime les valeurs d'un trou par régression sur les voisines.

    Seules les voisines qui ont une mesure chaque jour du trou sont utilisées.
    Modèle : T_cible = a1*T_v1 + ... + ak*T_vk + b, ajusté sur les jours où
    la cible et ces voisines ont une observation réelle.

    Args:
        cible: Mesures réelles de la station (NaN ailleurs).
        voisines_alignees: Mesures réelles des voisines, une colonne par voisine,
            alignées sur les jours de la station.
        jours_trou: Index des jours du trou à combler.

    Returns:
        Série des valeurs estimées sur les jours du trou, ou None si aucune
        voisine n'est utilisable ou s'il y a trop peu de jours communs.
    """
    utilisables = [
        v for v in voisines_alignees.columns if voisines_alignees.loc[jours_trou, v].notna().all()
    ]
    if not utilisables:
        return None

    voisines_utilisables = voisines_alignees[utilisables]
    periode_ajustement = cible.notna() & voisines_utilisables.notna().all(axis=1)
    if periode_ajustement.sum() < SEUIL_JOURS_AJUSTEMENT_REGRESSION:
        return None

    x_ajustement = np.column_stack(
        [voisines_utilisables[periode_ajustement].to_numpy(), np.ones(periode_ajustement.sum())]
    )
    y_ajustement = cible[periode_ajustement].to_numpy()
    coefficients, *_ = np.linalg.lstsq(x_ajustement, y_ajustement, rcond=None)

    x_trou = np.column_stack(
        [voisines_utilisables.loc[jours_trou].to_numpy(), np.ones(len(jours_trou))]
    )
    return pd.Series(x_trou @ coefficients, index=jours_trou)


def _combler_gaps_longs(
    grille: pd.DataFrame, pivots: dict[str, pd.DataFrame], voisines: list[str]
) -> pd.DataFrame:
    """Comble les trous de 8 à 30 jours par régression multi-station, trou par trou.

    Args:
        grille: Grille journalière d'une station.
        pivots: Observations réelles DATE x NUM_POSTE, par colonne.
        voisines: NUM_POSTE des stations voisines.

    Returns:
        Copie de la grille avec les valeurs comblées, source "estimee_8_30j".
    """
    grille = grille.copy()
    for colonne in COLONNES_A_COMBLER:
        eligible = grille[colonne].isna() & grille[f"LONGUEUR_TROU_{colonne}"].between(
            LIMITE_GAP_MOYEN + 1, LIMITE_GAP_LONG
        )
        if not eligible.any():
            continue

        # Seules les mesures réelles servent à l'ajustement, pas les valeurs déjà comblées
        cible = grille[colonne].where(grille[f"SOURCE_{colonne}"] == "observee")
        voisines_alignees = (
            pivots[colonne].reindex(index=grille["DATE"], columns=voisines).set_axis(grille.index)
        )

        # Les jours consécutifs d'un même trou reçoivent le même numéro
        numeros_trou = (eligible != eligible.shift()).cumsum()
        for numero in numeros_trou[eligible].unique():
            jours_trou = grille.index[eligible & (numeros_trou == numero)]
            estimation = _regression_sur_trou(cible, voisines_alignees, jours_trou)
            if estimation is not None:
                grille.loc[jours_trou, colonne] = estimation
                grille.loc[jours_trou, f"SOURCE_{colonne}"] = "estimee_8_30j"
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


def _retirer_incoherences(grille: pd.DataFrame) -> pd.DataFrame:
    """Retire les valeurs comblées qui donnent TMIN > TMAX.

    TMIN et TMAX sont comblés séparément et peuvent donc se croiser. Seules
    les valeurs comblées sont retirées : une mesure réelle est toujours gardée.

    Args:
        grille: Grille journalière de toutes les stations, après comblement.

    Returns:
        Copie de la grille avec la source "rejetee_tmin_sup_tmax" sur ces valeurs.
    """
    grille = grille.copy()
    incoherent = grille["TMIN"] > grille["TMAX"]
    for colonne in COLONNES_A_COMBLER:
        a_retirer = incoherent & (grille[f"SOURCE_{colonne}"] != "observee")
        grille.loc[a_retirer, colonne] = np.nan
        grille.loc[a_retirer, f"SOURCE_{colonne}"] = "rejetee_tmin_sup_tmax"
    return grille


def traiter_valeurs_manquantes(df: pd.DataFrame) -> pd.DataFrame:
    """Comble les valeurs manquantes de TMIN et TMAX.

    Args:
        df: DataFrame consolidé, une ligne par station et par jour.

    Returns:
        DataFrame sur calendrier journalier complet, avec les colonnes de
        suivi LONGUEUR_TROU_* et SOURCE_*.
    """
    # Retire les jours sans aucune température : les stations qui ne mesurent
    # que la pluie disparaissent, et chaque station ne couvre plus que la
    # période où elle mesure vraiment la température.
    df = df.dropna(subset=COLONNES_A_COMBLER, how="all")

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
    return _retirer_incoherences(grille)


def main() -> None:
    df_brut = pd.read_parquet(FICHIER_BRUT)
    # Colonnes encore présentes dans un Parquet brut généré par une ancienne version de meteo.py
    df_brut = df_brut.drop(columns=["TMEAN", "TMED_TN_TX"], errors="ignore")

    df = traiter_valeurs_manquantes(df_brut)
    # Les jours sans aucune température (trous rejetés) ne servent pas en base
    df = df[df["TMIN"].notna() | df["TMAX"].notna()]
    df = df.drop(columns=[f"LONGUEUR_TROU_{c}" for c in COLONNES_A_COMBLER])

    print("SOURCE_TMIN :\n", df["SOURCE_TMIN"].value_counts())
    print("SOURCE_TMAX :\n", df["SOURCE_TMAX"].value_counts())

    df.to_parquet(FICHIER_NETTOYE, index=False)
    print(f"Fichier écrit : {FICHIER_NETTOYE} ({len(df):,} lignes)")


if __name__ == "__main__":
    main()
