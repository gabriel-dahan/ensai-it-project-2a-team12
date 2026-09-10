import os
import pandas as pd
import requests

# ==========================================
# CONFIGURATION
# ==========================================
DOSSIER_DESTINATION = (
    "/home/onyxia/work/ensai-it-project-2a-team12/data/raw_data"
)

# Dictionnaire associant chaque département à son URL directe (.csv.gz)
CIBLES_METEO = {
    "01": "https://www.data.gouv.fr/api/1/datasets/r/c79aaafe-8017-4d2b-8884-57b5391da5bc",
    "02": "https://www.data.gouv.fr/api/1/datasets/r/e8cafb02-248c-41c1-a409-8eb5aaf4a102",
    "03": "https://www.data.gouv.fr/api/1/datasets/r/777fe96d-987e-4e31-ad67-3a8991849263",
    "04": "https://www.data.gouv.fr/api/1/datasets/r/eee4b43d-0cc0-4242-8929-10ee9cc67596",
    "05": "https://www.data.gouv.fr/api/1/datasets/r/edde6d8d-e026-4dfa-94aa-2a1d5c3c5eac",
    "06": "https://www.data.gouv.fr/api/1/datasets/r/ce6518fa-4831-4b31-91eb-7f41c354ef58",
    "07": "https://www.data.gouv.fr/api/1/datasets/r/7f708a21-f6f1-46a7-bee2-a331a579e628",
    "08": "https://www.data.gouv.fr/api/1/datasets/r/2ff1a5db-00a3-4f1b-b74e-f898bbb8cab6",
    "09": "https://www.data.gouv.fr/api/1/datasets/r/e98c097b-a150-4737-9805-c7fb6e71eeec",
    "10": "https://www.data.gouv.fr/api/1/datasets/r/48186700-71f2-4153-b0b5-b4932b3a670e",
    "11": "https://www.data.gouv.fr/api/1/datasets/r/f5e1ccf2-1ea5-457e-b4fb-7533ae7f9cfb",
    "12": "https://www.data.gouv.fr/api/1/datasets/r/48c22288-7cfc-4f9b-8cd6-081ef314165d",
    "13": "https://www.data.gouv.fr/api/1/datasets/r/5669e5be-8c67-4fbf-aeae-08cbc2369dd4",
    "14": "https://www.data.gouv.fr/api/1/datasets/r/5feeb9de-d9d3-4ab6-85b4-46bc09ac285a",
    "15": "https://www.data.gouv.fr/api/1/datasets/r/587f0b40-ffbb-4a90-83a5-b3b974757bba",
    "16": "https://www.data.gouv.fr/api/1/datasets/r/b8c9b479-e535-457d-9192-094c8a571c12",
    "17": "https://www.data.gouv.fr/api/1/datasets/r/daf5843a-7d1e-4b41-bf8e-220fddffa7ed",
    "18": "https://www.data.gouv.fr/api/1/datasets/r/43d95da3-997f-4766-b7e4-411d39288364",
    "19": "https://www.data.gouv.fr/api/1/datasets/r/b870e655-5386-49d4-ba48-920ceb3765f2",
    "20": "https://www.data.gouv.fr/api/1/datasets/r/24151d9c-1961-4edb-aff9-d3105867f40e",
    "21": "https://www.data.gouv.fr/api/1/datasets/r/4b31e0a6-39d6-445c-a283-16d05b078064",
    "22": "https://www.data.gouv.fr/api/1/datasets/r/ecda48c2-f09e-4509-951d-e16abe42a872",
    "23": "https://www.data.gouv.fr/api/1/datasets/r/6b837356-73a6-4e76-9923-d5f91e2ca122",
    "24": "https://www.data.gouv.fr/api/1/datasets/r/011f61cc-6789-44ed-bc9a-dad67c1c1039",
    "25": "https://www.data.gouv.fr/api/1/datasets/r/929aa82d-3592-4db3-ad90-e1adce979af7",
    "26": "https://www.data.gouv.fr/api/1/datasets/r/bbbc093d-f889-4eb4-9db3-6b5c67cbc563",
    "27": "https://www.data.gouv.fr/api/1/datasets/r/f4cb9bb9-bb80-41b1-b240-187889d164b8",
    "28": "https://www.data.gouv.fr/api/1/datasets/r/59bc2716-1007-4c2b-bed1-0ba79fc64404",
    "29": "https://www.data.gouv.fr/api/1/datasets/r/8349df0f-a964-4ddb-b4b2-9b8ea09ad970",
    "30": "https://www.data.gouv.fr/api/1/datasets/r/55264b89-1075-497e-8597-9c63422e6f66",
    "31": "https://www.data.gouv.fr/api/1/datasets/r/e518d10b-8100-49dd-953b-b057610b7949",
    "32": "https://www.data.gouv.fr/api/1/datasets/r/7cd382a6-f8e9-42d3-85ba-97088e028ffe",
    "33": "https://www.data.gouv.fr/api/1/datasets/r/b0e78f3d-9085-4d6d-a47d-6d942f5e9a54",
    "34": "https://www.data.gouv.fr/api/1/datasets/r/8ad3f9d4-5324-4c74-ae2f-e8b8a89684af",
    "35": "https://www.data.gouv.fr/api/1/datasets/r/8051582c-2f1b-41c6-85a5-2f7f98389193",
    "36": "https://www.data.gouv.fr/api/1/datasets/r/04679829-40f1-4bd2-bb82-23ad526cd95d",
    "37": "https://www.data.gouv.fr/api/1/datasets/r/62d5d1eb-1ef2-43a5-9bdf-e0b8a67cc6ad",
    "38": "https://www.data.gouv.fr/api/1/datasets/r/e2b0446d-ce6a-4340-b42b-4f33ed227c30",
    "39": "https://www.data.gouv.fr/api/1/datasets/r/62ee582e-7a3f-43f7-bb1f-eb470ae90d2f",
    "40": "https://www.data.gouv.fr/api/1/datasets/r/8b2d56fc-40df-44b2-9281-7794017d341c",
    "41": "https://www.data.gouv.fr/api/1/datasets/r/c20e431a-98e9-4626-b46a-95a8a9d2d64a",
    "42": "https://www.data.gouv.fr/api/1/datasets/r/1ed16fc8-31a5-4ef5-b8ca-d32d5b3f4224",
    "43": "https://www.data.gouv.fr/api/1/datasets/r/8a4c6cd9-ca20-4913-b541-544f44d73218",
    "44": "https://www.data.gouv.fr/api/1/datasets/r/6038690c-e555-491f-8588-b595a08c8f67",
    "45": "https://www.data.gouv.fr/api/1/datasets/r/09f30cdc-603a-4992-a36a-c36d9201072c",
    "46": "https://www.data.gouv.fr/api/1/datasets/r/00786c56-23ce-4c05-b91a-97e1faeefb76",
    "47": "https://www.data.gouv.fr/api/1/datasets/r/7e53e7ec-f71a-43ce-ab93-d31d4f8d0f94",
    "48": "https://www.data.gouv.fr/api/1/datasets/r/3ab96225-990e-4059-beef-bdf8a9047e12",
    "49": "https://www.data.gouv.fr/api/1/datasets/r/999fe6f2-8de2-4a6f-ae83-d454ac2400d3",
    "50": "https://www.data.gouv.fr/api/1/datasets/r/582886d0-6f6b-427f-a480-5e82c29de1bd",
    "51": "https://www.data.gouv.fr/api/1/datasets/r/cd325707-73e3-4f43-b7ad-a7107003b96f",
    "52": "https://www.data.gouv.fr/api/1/datasets/r/224aac45-1e67-4278-9b66-c1a92a0fc765",
    "53": "https://www.data.gouv.fr/api/1/datasets/r/a5d089b3-746f-4a2c-b116-58d484cad6c3",
    "54": "https://www.data.gouv.fr/api/1/datasets/r/34aa794a-ff21-47aa-8f27-7d5ea36ed80d",
    "55": "https://www.data.gouv.fr/api/1/datasets/r/5c7a4b87-aa26-4c88-9f03-f6986532ca91",
    "56": "https://www.data.gouv.fr/api/1/datasets/r/570b8bec-5e45-4276-8738-bc0aa82f782a",
    "57": "https://www.data.gouv.fr/api/1/datasets/r/d73f912b-3ac1-4daa-9e3f-587afa6f7887",
    "58": "https://www.data.gouv.fr/api/1/datasets/r/83060285-3dbf-40d5-81ea-f873ecb971e1",
    "59": "https://www.data.gouv.fr/api/1/datasets/r/c2a9f75c-0554-48d6-ba1a-534b00063f89",
    "60": "https://www.data.gouv.fr/api/1/datasets/r/8a9591a0-a4b1-4e3e-8610-85540c18d643",
    "61": "https://www.data.gouv.fr/api/1/datasets/r/f07defc4-3281-4104-a468-07807fe43126",
    "62": "https://www.data.gouv.fr/api/1/datasets/r/aec69332-1f0a-470f-818a-660d8ade34aa",
    "63": "https://www.data.gouv.fr/api/1/datasets/r/4e176848-0138-47c4-ac26-98333d938326",
    "64": "https://www.data.gouv.fr/api/1/datasets/r/8f62ed7c-1d50-4812-9a1d-b549e9f92a33",
    "65": "https://www.data.gouv.fr/api/1/datasets/r/e7a5a7dd-a1f2-47e6-afed-01133b915051",
    "66": "https://www.data.gouv.fr/api/1/datasets/r/a095e27f-81eb-4dfa-bfc4-ad01dd0390cd",
    "67": "https://www.data.gouv.fr/api/1/datasets/r/ea9a0c19-5519-470e-bb5e-ede4b3301268",
    "68": "https://www.data.gouv.fr/api/1/datasets/r/3d49c539-436f-4893-b5c7-d857fc5edca7",
    "69": "https://www.data.gouv.fr/api/1/datasets/r/8dc3b3c0-4edd-4d28-bdd0-4eb2a85aa0d5",
    "70": "https://www.data.gouv.fr/api/1/datasets/r/21e70347-f89c-4b45-a409-61b4add6c365",
    "71": "https://www.data.gouv.fr/api/1/datasets/r/6101e0eb-2ef5-400f-9b18-87adf71ac572",
    "72": "https://www.data.gouv.fr/api/1/datasets/r/98e625c2-58f3-4767-88a6-16fce78c4d4b",
    "73": "https://www.data.gouv.fr/api/1/datasets/r/828ec510-e062-48e4-9370-0bd9a5f65a9c",
    "74": "https://www.data.gouv.fr/api/1/datasets/r/23a368d7-59e3-488d-afb7-3890f972dcd7",
    "75": "https://www.data.gouv.fr/api/1/datasets/r/27bf7b0f-62a8-438f-acf4-b5f58d293322",
    "76": "https://www.data.gouv.fr/api/1/datasets/r/83047d20-9b28-4734-9aca-1a44801353ee",
    "77": "https://www.data.gouv.fr/api/1/datasets/r/36a85491-dfb8-45e3-96fa-561158ee34dd",
    "78": "https://www.data.gouv.fr/api/1/datasets/r/a7c4b4a1-6b99-46ec-8ca1-b2e368e63a59",
    "79": "https://www.data.gouv.fr/api/1/datasets/r/0f019547-c446-4d08-930f-9970cfa9b97b",
    "80": "https://www.data.gouv.fr/api/1/datasets/r/59dd29dd-42c1-480a-83a4-cedc80082816",
    "81": "https://www.data.gouv.fr/api/1/datasets/r/c2679caa-f430-4d59-8451-696dd43f8e80",
    "82": "https://www.data.gouv.fr/api/1/datasets/r/0d30a20b-7448-4524-8507-6f5765d37b71",
    "83": "https://www.data.gouv.fr/api/1/datasets/r/ffe62e95-57f0-4135-9e28-e95d2e31dede",
    "84": "https://www.data.gouv.fr/api/1/datasets/r/25e1be54-9384-4632-a5f2-db8f463d3d65",
    "85": "https://www.data.gouv.fr/api/1/datasets/r/d5d3514d-867b-4529-a031-1f5e840f816a",
    "86": "https://www.data.gouv.fr/api/1/datasets/r/b69b1bf4-ae45-4061-a10b-8f2a5ed6bafd",
    "87": "https://www.data.gouv.fr/api/1/datasets/r/29a456ec-2ce9-4ce1-ba23-4ec3e8b25324",
    "88": "https://www.data.gouv.fr/api/1/datasets/r/4343f20d-401d-40cd-82cc-5528fdb66c0d",
    "89": "https://www.data.gouv.fr/api/1/datasets/r/e26211d0-598c-41d4-a342-ec059b9df660",
    "90": "https://www.data.gouv.fr/api/1/datasets/r/6969896a-c507-47eb-a3b8-cc8424abd3b3",
    "91": "https://www.data.gouv.fr/api/1/datasets/r/04a75839-25fd-46b6-af09-e1934388cef7",
    "92": "https://www.data.gouv.fr/api/1/datasets/r/8fc12852-f9b9-47fd-8052-d58cc5ee6a63",
    "93": "https://www.data.gouv.fr/api/1/datasets/r/77927e93-9aa1-462c-bacb-bfff81c8ed48",
    "94": "https://www.data.gouv.fr/api/1/datasets/r/f302db14-f490-4f73-adf7-a8458ecf1da3",
    "95": "https://www.data.gouv.fr/api/1/datasets/r/c65b7105-6824-4f2e-b53a-66934fbe863b",
    "971": "https://www.data.gouv.fr/api/1/datasets/r/1d2a89ae-aa3c-4c12-aa44-c3f148e5463c",
    "972": "https://www.data.gouv.fr/api/1/datasets/r/72654028-7f2f-4588-8dd6-67c52093e699",
    "973": "https://www.data.gouv.fr/api/1/datasets/r/18a64ac1-54cc-440e-900f-312b525fd0a7",
    "974": "https://www.data.gouv.fr/api/1/datasets/r/fe8b9ae4-885c-4a12-98b4-af3ec330103f",
    "975": "https://www.data.gouv.fr/api/1/datasets/r/b797b190-4d81-4a59-8117-ac9a88785742",
    "984": "https://www.data.gouv.fr/api/1/datasets/r/02c60c03-eeea-4719-9adb-5f4c4bf329d0",
    "985": "https://www.data.gouv.fr/api/1/datasets/r/a3f6b4b7-6e8c-4f9f-a9e5-e3d75316a955",
    "986": "https://www.data.gouv.fr/api/1/datasets/r/f7693142-8338-4334-823a-947d064ef63e",
    "987": "https://www.data.gouv.fr/api/1/datasets/r/ca490340-a5fd-4a59-ae32-611783a59b17",
    "988": "https://www.data.gouv.fr/api/1/datasets/r/1d03ec62-9b90-45b7-8199-d1c3a3c666e8",
    "99": "https://www.data.gouv.fr/api/1/datasets/r/ee873c76-cc9f-4fd0-a752-f9d2283a5d0f",
}

# ==========================================
# FONCTION DE FILTRAGE
# ==========================================


def filtrer_donnees_meteo(chemin_gz):
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
    df = df[df["DATE"] >= "20000101"]

    renommage = {
        "TN": "TMIN",
        "TX": "TMAX",
        "TM": "TMEAN",
        "TNTXM": "TMED_TN_TX",
    }
    df = df.rename(columns=renommage)

    return df


# ==========================================
# EXÉCUTION : TÉLÉCHARGEMENT, FILTRAGE ET NETTOYAGE
# ==========================================
os.makedirs(DOSSIER_DESTINATION, exist_ok=True)
dict_meteo = {}

for dept, url in CIBLES_METEO.items():
    if not url or "..." in url:
        print(f"URL non renseignée pour le département {dept}.")
        continue

    print(f"Traitement du département {dept}...")
    response = requests.get(url)

    if response.status_code == 200:
        chemin_gz = os.path.join(DOSSIER_DESTINATION, f"dep_{dept}.csv.gz")

        # 1. Sauvegarde temporaire du fichier compressé unique
        with open(chemin_gz, "wb") as f:
            f.write(response.content)

        try:
            # 2. Lecture, filtrage direct en DataFrame et stockage dans le dictionnaire
            dict_meteo[dept] = filtrer_donnees_meteo(chemin_gz)
            print(
                f"Département {dept} chargé, filtré et stocké dans dict_meteo."
            )
        except Exception as e:
            print(f"Erreur lors du traitement du département {dept}: {e}")
        finally:
            # 3. Suppression immédiate du fichier sur le disque pour libérer l'espace
            if os.path.exists(chemin_gz):
                os.remove(chemin_gz)
                print(f"Fichier temporaire du département {dept} supprimé.")
    else:
        print(
            f"Erreur de téléchargement (Code {response.status_code}) pour le"
            f" département {dept}"
        )

    