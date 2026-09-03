import pandas as pd


def filtrer_donnees_meteo(chemin_csv):

    df = pd.read_csv(chemin_csv, sep=";", low_memory=False)

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
    df = df[df["DATE"] >= "20000101"]

    renommage = {
      "TN": "TMIN",
      "TX": "TMAX",
      "TM": "TMEAN",
      "TNTXM": "TMED_TN_TX",
      }
    df = df.rename(columns=renommage)

    return df


departements = [
    "01",
    "02",
    "03",
    "04",
    "05",
    "06",
    "07",
    "08",
    "09",
    "10",
    "11",
    "12",
    "13",
    "14",
    "15",
    "16",
    "17",
    "18",
    "19",
    "2A",
    "2B",
    "21",
    "22",
    "23",
    "24",
    "25",
    "26",
    "27",
    "28",
    "29",
    "30",
    "31",
    "32",
    "33",
    "34",
    "35",
    "36",
    "37",
    "38",
    "39",
    "40",
    "41",
    "42",
    "43",
    "44",
    "45",
    "46",
    "47",
    "48",
    "49",
    "50",
    "51",
    "52",
    "53",
    "54",
    "55",
    "56",
    "57",
    "58",
    "59",
    "60",
    "61",
    "62",
    "63",
    "64",
    "65",
    "66",
    "67",
    "68",
    "69",
    "70",
    "71",
    "72",
    "73",
    "74",
    "75",
    "76",
    "77",
    "78",
    "79",
    "80",
    "81",
    "82",
    "83",
    "84",
    "85",
    "86",
    "87",
    "88",
    "89",
    "90",
    "91",
    "92",
    "93",
    "94",
    "95",
    "971",
    "972",
    "973",
    "974",
    "975",
    "984",
    "985",
    "986",
    "987",
    "988",
    "99"
]
# Dictionnaire vide pour stocker tous les DataFrames proprement
dict_meteo = {}

# Boucle simple pour remplir le dictionnaire
for dept in departements:
    chemin = f"/home/onyxia/work/meteo_raw_data/QUOT_departement_{dept}_periode_1950-2024_RR-T-Vent.csv.gz"

    try:
        dict_meteo[dept] = filtrer_donnees_meteo(chemin)
    except FileNotFoundError:
        print(f"Fichier manquant pour le département {dept}")
