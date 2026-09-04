import pandas as pd
import requests

# 1. Récupération des communes
url_geo = "https://geo.api.gouv.fr/communes?fields=nom,codesPostaux,centre,departement,region&format=json"
# On télécharge les communes qui ont bien des coordonnées
communes = [c for c in requests.get(url_geo).json() if 'centre' in c]

donnees = []
url_alti = "https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json"

print(f"Début du traitement de {len(communes)} communes...")

# 2. Boucle par lots de 250
for i in range(0, len(communes), 250):
    lot = communes[i:i+250]

    # Préparation des coordonnées groupées
    lons = "|".join([str(c['centre']['coordinates'][0]) for c in lot])
    lats = "|".join([str(c['centre']['coordinates'][1]) for c in lot])

    # Appel à l'API Altimétrique avec la méthode GET
    url_get = f"{url_alti}?lon={lons}&lat={lats}"

    try:
        response = requests.get(url_get)
        if response.status_code == 200:
            altis = response.json().get('elevations', [])
        else:
            print(f"Erreur API sur le lot {i}: {response.status_code}")
            altis = []
    except Exception as e:
        print(f"Erreur réseau sur le lot {i}: {e}")
        altis = []

    # Rassemblement des données
    for j, c in enumerate(lot):
        # SÉCURITÉ : On vérifie si la commune possède un code postal avant de prendre le premier
        liste_cp = c.get('codesPostaux', [])
        code_postal_securise = liste_cp[0] if len(liste_cp) > 0 else ""

        altitude = altis[j].get('z') if j < len(altis) else None

        donnees.append({
            'Commune': c.get('nom'),
            'Code_Postal': code_postal_securise,
            'Dept': c.get('departement', {}).get('code'),
            'Region': c.get('region', {}).get('code'),
            'Lon': c['centre']['coordinates'][0],
            'Lat': c['centre']['coordinates'][1],
            'Altitude': altitude
        })
    print(f"Progression : {min(i + 250, len(communes))} / {len(communes)}")

# 3. Sauvegarde
print("Création du fichier CSV...")
df = pd.DataFrame(donnees)
df.to_csv("communes.csv", index=False, sep=';', encoding='utf-8-sig')
print("Fichier communes.csv généré avec succès !")
