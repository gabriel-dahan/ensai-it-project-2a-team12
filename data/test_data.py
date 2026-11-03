"""Tests des scripts de préparation des données (meteo, qualite_meteo, communes, init_db).

Aucun test n'utilise le réseau ni une vraie base PostgreSQL : les données sont
construites à la main, et la base est remplacée par un faux objet connexion.

Lancement depuis la racine du dépôt : pytest data/test_data.py
"""

import gzip

import numpy as np
import pandas as pd
import pytest

import communes
import init_db
import meteo
import qualite_meteo


def _station(num_poste, tmin, tmax, lat=45.0, lon=5.0, debut="2020-01-01"):
    """Relevés d'une station : un jour par valeur de `tmin`, à partir de `debut`."""
    return pd.DataFrame(
        {
            "NUM_POSTE": num_poste,
            "NOM_USUEL": f"STATION {num_poste}",
            "LAT": lat,
            "LON": lon,
            "ALTI": 100.0,
            "DATE": pd.date_range(debut, periods=len(tmin), freq="D"),
            "TMIN": tmin,
            "TMAX": tmax,
        }
    )


def _ligne(resultat, num_poste, jour):
    """Ligne du résultat pour une station et un numéro de jour (0 = 2020-01-01)."""
    date = pd.Timestamp("2020-01-01") + pd.Timedelta(days=jour)
    return resultat[(resultat["NUM_POSTE"] == num_poste) & (resultat["DATE"] == date)].iloc[0]


# --- meteo.py ---


def test_filtrer_donnees_meteo(tmp_path):
    """Garde le zéro initial du code, retire les dates avant 1990 et les colonnes inutiles."""
    contenu = (
        "NUM_POSTE;NOM_USUEL;LAT;LON;ALTI;AAAAMMJJ;RR;TN;TX;TM\n"
        "01014002;BÉZIERS;46.27;5.66;534;19891231;0.0;1.0;5.0;3.0\n"
        "01014002;BÉZIERS;46.27;5.66;534;19900101;0.0;-2.5;4.0;0.7\n"
    )
    chemin = tmp_path / "Q_01.csv.gz"
    with gzip.open(chemin, "wb") as f:
        f.write(contenu.encode("latin1"))

    df = meteo.filtrer_donnees_meteo(chemin)

    assert len(df) == 1
    assert df["NUM_POSTE"].iloc[0] == "01014002"
    assert df["NOM_USUEL"].iloc[0] == "BÉZIERS"
    assert df["TMIN"].iloc[0] == -2.5
    assert list(df.columns) == ["NUM_POSTE", "DATE", "NOM_USUEL", "TMIN", "TMAX", "LAT", "LON", "ALTI"]


# --- qualite_meteo.py : fonctions élémentaires ---


def test_longueur_trou():
    masque = pd.Series([False, True, True, False, True])
    longueurs = qualite_meteo._longueur_trou(masque)
    assert longueurs.fillna(-1).tolist() == [-1, 2, 2, -1, 1]


def test_distance_paris_lyon():
    assert abs(qualite_meteo._distance_km(48.8566, 2.3522, 45.7640, 4.8357) - 392) < 5
    assert qualite_meteo._distance_km(45.0, 5.0, 45.0, 5.0) == 0


def test_voisines_a_moins_de_50_km():
    """Une station trop éloignée n'est pas une voisine ; une station isolée n'en a aucune."""
    grille = pd.DataFrame(
        {
            "NUM_POSTE": ["01", "02", "03"],
            "LAT": [45.0, 45.1, 46.0],  # 02 est à environ 11 km de 01, 03 à plus de 100 km
            "LON": [5.0, 5.0, 5.0],
        }
    )
    voisinage = qualite_meteo._calculer_voisinage(grille, 5)
    assert voisinage["01"] == ["02"]
    assert voisinage["03"] == []


def test_retirer_incoherences():
    """Une valeur comblée qui donne TMIN > TMAX est retirée, une mesure réelle est gardée."""
    grille = pd.DataFrame(
        {
            "TMIN": [5.0, 5.0, 1.0],
            "TMAX": [3.0, 3.0, 8.0],
            "SOURCE_TMIN": ["interpolee_1_2j", "observee", "observee"],
            "SOURCE_TMAX": ["observee", "observee", "observee"],
        }
    )
    resultat = qualite_meteo._retirer_incoherences(grille)

    assert np.isnan(resultat.loc[0, "TMIN"])
    assert resultat.loc[0, "SOURCE_TMIN"] == "rejetee_tmin_sup_tmax"
    assert resultat.loc[0, "TMAX"] == 3.0
    assert resultat.loc[1, "TMIN"] == 5.0
    assert resultat.loc[2, "SOURCE_TMIN"] == "observee"


# --- qualite_meteo.py : traitement complet ---


def test_trou_court_interpole():
    df = _station("01", tmin=[10.0, np.nan, 14.0], tmax=[20.0, 21.0, 22.0])
    resultat = qualite_meteo.traiter_valeurs_manquantes(df)
    ligne = _ligne(resultat, "01", 1)
    assert ligne["TMIN"] == 12.0
    assert ligne["SOURCE_TMIN"] == "interpolee_1_2j"


def test_trou_en_debut_de_serie_non_comble():
    """Pas d'extrapolation : sans valeur avant le trou, la valeur reste manquante."""
    df = _station("01", tmin=[np.nan, 3.0, 4.0], tmax=[5.0, 6.0, 7.0])
    resultat = qualite_meteo.traiter_valeurs_manquantes(df)
    ligne = _ligne(resultat, "01", 0)
    assert np.isnan(ligne["TMIN"])
    assert ligne["SOURCE_TMIN"] == "manquante"


def test_station_pluie_seule_retiree():
    df = pd.concat(
        [
            _station("01", tmin=[1.0, 2.0], tmax=[5.0, 6.0]),
            _station("02", tmin=[np.nan, np.nan], tmax=[np.nan, np.nan]),
        ]
    )
    resultat = qualite_meteo.traiter_valeurs_manquantes(df)
    assert resultat["NUM_POSTE"].unique().tolist() == ["01"]


def test_jours_absents_ajoutes_puis_trou_trop_long_rejete():
    """Les jours sans ligne sont recréés ; un trou de plus de 30 jours n'est pas comblé."""
    df = pd.concat(
        [
            _station("01", tmin=[1.0], tmax=[5.0], debut="2020-01-01"),
            _station("01", tmin=[2.0], tmax=[6.0], debut="2020-02-06"),
        ]
    )
    resultat = qualite_meteo.traiter_valeurs_manquantes(df)

    assert len(resultat) == 37  # du 1er janvier au 6 février inclus
    ligne = _ligne(resultat, "01", 10)
    assert np.isnan(ligne["TMIN"])
    assert ligne["SOURCE_TMIN"] == "rejetee_gap_trop_long"


def test_trou_moyen_voisine_corrigee_de_son_ecart():
    """Trou de 4 jours : la voisine, 5 °C plus froide, est ramenée au niveau de la station.

    La série est linéaire, donc la valeur comblée doit être exactement la vraie valeur
    (sans la correction de l'écart, on obtiendrait 1,5 °C de moins).
    """
    jours = np.arange(60)
    vrai_tmin = 0.5 * jours
    tmin_a = vrai_tmin.copy()
    tmin_a[20:24] = np.nan
    df = pd.concat(
        [
            _station("A", tmin=tmin_a, tmax=tmin_a + 10, lat=45.0),
            _station("B", tmin=vrai_tmin - 5, tmax=vrai_tmin + 5, lat=45.1),
        ]
    )
    resultat = qualite_meteo.traiter_valeurs_manquantes(df)

    ligne = _ligne(resultat, "A", 21)
    assert ligne["SOURCE_TMIN"] == "interpolee_3_7j"
    assert ligne["TMIN"] == pytest.approx(vrai_tmin[21])


def test_trou_long_comble_par_regression():
    """Trou de 10 jours : la station vaut toujours 2 x la voisine + 1, la régression le retrouve."""
    jours = np.arange(80)
    tmin_b = 10 * np.sin(jours / 5)
    tmin_a = 2 * tmin_b + 1
    tmin_a[40:50] = np.nan
    df = pd.concat(
        [
            _station("A", tmin=tmin_a, tmax=tmin_a + 30, lat=45.0),
            _station("B", tmin=tmin_b, tmax=tmin_b + 15, lat=45.1),
        ]
    )
    resultat = qualite_meteo.traiter_valeurs_manquantes(df)

    ligne = _ligne(resultat, "A", 45)
    assert ligne["SOURCE_TMIN"] == "estimee_8_30j"
    assert ligne["TMIN"] == pytest.approx(2 * tmin_b[45] + 1)


def test_trou_long_sans_voisine_utilisable():
    """Si la seule voisine a aussi un trou pendant ces jours, rien n'est inventé."""
    jours = np.arange(80)
    tmin = 10 * np.sin(jours / 5)
    tmin[40:50] = np.nan
    df = pd.concat(
        [
            _station("A", tmin=tmin, tmax=tmin + 10, lat=45.0),
            _station("B", tmin=tmin - 2, tmax=tmin + 8, lat=45.1),
        ]
    )
    resultat = qualite_meteo.traiter_valeurs_manquantes(df)

    ligne = _ligne(resultat, "A", 45)
    assert np.isnan(ligne["TMIN"])
    assert ligne["SOURCE_TMIN"] == "manquante"


# --- communes.py ---


@pytest.mark.parametrize(
    "commune, attendu",
    [
        ({"mairie": {"coordinates": [6.87, 45.92]}, "centre": {"coordinates": [6.93, 45.93]}}, [6.87, 45.92]),
        ({"centre": {"coordinates": [6.93, 45.93]}}, [6.93, 45.93]),
        ({"mairie": None, "centre": {"coordinates": [6.93, 45.93]}}, [6.93, 45.93]),
    ],
)
def test_coordonnees_mairie_sinon_centre(commune, attendu):
    assert communes._coordonnees(commune) == attendu


# --- init_db.py ---


class _FauxCurseur:
    """Remplace un curseur psycopg2 : garde le texte envoyé par COPY."""

    def __init__(self, connexion):
        self.connexion = connexion

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def copy_expert(self, requete, tampon):
        self.connexion.csv_recu += tampon.read()


class _FausseConnexion:
    def __init__(self):
        self.csv_recu = ""

    def cursor(self):
        return _FauxCurseur(self)

    def commit(self):
        pass


def test_lignes_convertit_en_types_python():
    """psycopg2 ne sait pas insérer les types numpy ni NaN : ils deviennent int, float et None."""
    df = pd.DataFrame({"a": [1, 2], "b": [1.5, np.nan], "c": ["x", None]})
    lignes = init_db._lignes(df)
    assert lignes == [(1, 1.5, "x"), (2, None, None)]
    assert type(lignes[0][0]) is int


def test_charger_releves():
    """Les jours sans aucune température ne sont pas insérés, une valeur absente devient vide."""
    meteo_df = pd.DataFrame(
        {
            "NUM_POSTE": ["01", "01", "01"],
            "DATE": pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"]),
            "TMIN": [1.0, np.nan, np.nan],
            "TMAX": [5.0, np.nan, 6.0],
            "SOURCE_TMIN": ["observee", "rejetee_gap_trop_long", "manquante"],
            "SOURCE_TMAX": ["observee", "rejetee_gap_trop_long", "observee"],
        }
    )
    connexion = _FausseConnexion()
    init_db.charger_releves(connexion, meteo_df, {"01": 7})

    assert connexion.csv_recu.splitlines() == [
        "7,2020-01-01,1.0,5.0,observee,observee",
        "7,2020-01-03,,6.0,manquante,observee",
    ]
