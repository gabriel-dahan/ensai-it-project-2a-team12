# État des lieux de l'API DJU par rapport à `new_diagram.md`

*3 novembre 2026, d'après le code de la branche `main` (commit `b05df7c0`).*

> **Mise à jour du 3 novembre 2026** : toutes les tâches cochées `[x]` ont été réalisées.
> - **Tests** : 87 tests passent (`cd api && ../.venv/bin/python -m pytest`).
> - **Vraie base** (données de la Bretagne) : F1, F2, F3, l'authentification, F4 et FO3 ont été vérifiés de bout en bout.
> - **Reste ouvert** : H7, qui demande une opération git manuelle. Les mises à jour de `new_diagram.md` listées en section 6 sont faites.
> - **Lecture** : les tableaux des sections 0, 3 et 4 décrivent l'état *avant* les corrections.

Ce document compare le code à [new_diagram.md](new_diagram.md), en suivant ses sections dans l'ordre : diagramme de classes, modèle de données, diagrammes de séquence, diagrammes d'activité. Les problèmes qui n'apparaissent dans aucun diagramme sont regroupés dans l'annexe (section 5).

**Méthode** : relecture de tout le code (`api/` et `data/`), puis démarrage de l'API avec le `TestClient` de FastAPI et appel de chaque route. Rien n'a été testé contre une vraie base PostgreSQL : les DAO ont seulement été relues.

**Légende**
- `[x]` conforme au diagramme · `[ ]` à faire
- **[Bug]** le code existe mais il est faux · **[Feature]** il manque du code · **[Nettoyage]** code absent du diagramme, à retirer
- Les identifiants (C = classes, M = modèle de données, H = hors diagrammes) servent de renvois dans les sections 3 et 4.

---

## 0. Résumé

| Fonctionnalité | État | Tâches principales |
|---|---|---|
| F0 : initialisation des données | 🟠 Partiel | M5, M6, M7 |
| F1 : DJU ponctuel | 🔴 Absent | C1, C4, C22, C25 |
| F2 : zonages officiels | 🔴 Absent | C5, M9 |
| F3 : DJU sur un territoire | 🔴 Absent | C2, C4, C7, C8, C26, C32, C33 |
| Connexion et inscription | 🟠 Partiel (DAO fini) | C13 |
| F4 : zonages personnalisés | 🔴 Absent | C9, C11, C12, C18, M9 |
| FO1 : cache | 🟠 Partiel (`DjuDao` fini) | M2, M11, M13, M14 |
| FO3 : import | 🔴 Absent | C10 |

**Les quatre bloquants à régler d'abord**
1. **H1** : l'API ne démarre pas, car la route d'import utilise un upload de fichier (`File`/`Form`) qui exige `python-multipart`. On supprime cet upload au lieu d'ajouter la bibliothèque (décision D5).
2. **C22** : la lecture des relevés plante (`station_id`).
3. **M7** : les scripts de données remplissent des tables que l'API ne lit pas.
4. **H2** : l'API ne charge pas le `.env`.

**Réponses des routes testées** (avec `python-multipart` installé à part) :

| Réponse | Routes |
|---|---|
| 200 | `/health` |
| 422 (format incorrect, comme prévu) | `/zones?type=foo` |
| 401 (comme prévu) | `/user/zones` sans jeton |
| 501 (non implémenté) | toutes les autres routes métier |

---

## 1. Diagramme de classes

### Services

**`DjuService`** ([dju_service.py](../api/src/service/dju_service.py))
- [x] **C1 [Feature]** `calculate_point_dju(request)` existe, mais renvoie 501. Il reçoit en plus un paramètre `user`, absent du diagramme : il faut le retirer ici et dans [dju_controller.py:41](../api/src/controllers/dju_controller.py#L41). À écrire :
  - le contrôle des paramètres (au moins un seuil, `start_date` ≤ `end_date`, sinon 400) ;
  - un `DjuType` par seuil ;
  - une seule estimation des températures ;
  - un `run()` par type ;
  - le résultat est renvoyé en `dict[str, DjuCalculation]`, indexé par mode.
- [x] **C2 [Feature]** `calculate_zone_dju(request, user)` a la bonne signature, mais renvoie 501. Il doit renvoyer une `list[DjuCalculation]`, avec un calcul par sous-zone et par type. Or `_to_response()` attend aujourd'hui un `dict` indexé par mode ([dju_controller.py:17](../api/src/controllers/dju_controller.py#L17)) : il faut l'adapter.
- [x] **C3 [Nettoyage]** Retirer `calculate_heating_dju()` et `calculate_cooling_dju()`, qui ne figurent pas dans le diagramme et font double emploi avec `DjuType.compute_daily_value()`.

**`TemperatureService`** ([temperature_service.py](../api/src/service/temperature_service.py), fichier vide)
- [x] **C4 [Feature]** Écrire les trois méthodes :
  - `find_candidate_stations(latitude, longitude, number_of_stations, period)` : les N stations les plus proches **qui ont des relevés sur la période** ;
  - `estimate_daily_temperatures(latitude, longitude, altitude, stations, period)` : correction d'altitude si l'altitude est connue, puis pondération inverse à la distance (poids 1/d²) jour par jour ;
  - `get_municipality_temperatures(municipality, period, number_of_stations, use_altitude)` : passe par le cache M2.

**`ZoneService`** ([zone_service.py](../api/src/service/zone_service.py))
- [x] **C5 [Feature]** `list_public_zones(zone_type)` renvoie 501.
- [x] **C6 [Feature]** `list_user_zonings(user)` renvoie 501.
- [x] **C7 [Feature]** `get_zone(zone_type, zone_id)` n'existe pas.
- [x] **C8 [Feature]** `get_sub_zones(zone, aggregation_level)` n'existe pas.
- [x] **C9 [Bug]** `create_zoning` renvoie 501 et n'a pas le paramètre `name` : le diagramme demande `(user, name, description, codes_insee)`.
- [x] **C10 [Feature]** `import_zoning(user, filename, content, description)` renvoie 501. Il faut lire les codes INSEE d'un fichier CSV ou JSON, puis suivre le même chemin que `create_zoning`. Le contenu du fichier arrive sous forme de texte dans un corps JSON, sans upload multipart (décision D5, voir H1). Pour le nom du zonage, voir la question Q5.
- [x] **C11 [Feature]** `update_zoning(user, zoning_id, description, add_codes_insee, remove_codes_insee)` a la bonne signature, mais renvoie 501.
- [x] **C12 [Feature]** `delete_zoning(user, zoning_id)` a la bonne signature, mais renvoie 501.

**`AuthService`** ([auth_service.py](../api/src/service/auth_service.py))
- [x] **C13 [Feature]** `register`, `authenticate` et `get_current_user` ont la bonne signature, mais renvoient 501. Choix retenu : un jeton JWT avec `pyjwt` (décision D1).

### Territoire ([geo_zone.py](../api/src/business_object/geo_zone.py))

- [x] `GeographicZone` : `id`, `name` et `get_municipalities()`.
- [x] **C14 [Bug]** `GeographicZone` déclare `id` et `name` une seconde fois, dont une ligne `id; Optional[str]` sans effet ([geo_zone.py:27-28](../api/src/business_object/geo_zone.py#L27-L28)).
- [x] **C15 [Nettoyage]** Rendre `GeographicZone` abstraite et retirer `contains_point()`. Pour `zone_type`, voir le point 6 de la section 6.
- [x] `Region` : `insee_code`, `get_municipalities()` et `add_department()`.
- [x] **C16 [Bug]** `Region.add_department()` est défini deux fois ([geo_zone.py:57](../api/src/business_object/geo_zone.py#L57) et [62](../api/src/business_object/geo_zone.py#L62)).
- [x] `Department` : `insee_code`, `get_municipalities()` et `add_municipality()`.
- [x] `Municipality` : `insee_code`, `latitude`, `longitude`, `altitude`, `population` et `distance_to()` (Haversine).
- [x] **C17 [Nettoyage]** Retirer `Municipality.stations` et `get_nearby_stations()` ([geo_zone.py:95-110](../api/src/business_object/geo_zone.py#L95-L110)).
- [x] `Zoning` : `description`, `created_at`, `add_municipality()` (sans doublon), `remove_municipality()` et `get_municipalities()`.
- [x] **C18 [Feature]** `Zoning.is_owned_by(user)` n'existe pas.

### Utilisateur ([user.py](../api/src/business_object/user.py))

- [x] `id`, `username`, mot de passe privé haché avec bcrypt, et `check_password()`. `from_storage()` relit un hash sans le hacher une seconde fois.
- [x] **C19 [Bug]** `create_zoning(description)` utilise la description comme nom. Le diagramme demande `create_zoning(name, description)` ([user.py:57](../api/src/business_object/user.py#L57)).
- [x] **C20 [Nettoyage]** Retirer `get_calculations()`, `add_calculation()` et `__calculations` ([user.py:65-70](../api/src/business_object/user.py#L65-L70)).

### Données météo

- [x] `MeteoStation` : `station_code`, `name`, `latitude`, `longitude`, `altitude` et `distance_to()`.
- [x] **C21 [Nettoyage]** Retirer `MeteoStation.reports` et `get_reports()` ([meteo_station.py:26-36](../api/src/business_object/meteo_station.py#L26-L36)).
- [x] `TemperatureReport` : `date`, `temp_min`, `temp_max`, et `apply_altitude_correction()` (-0,65 °C par 100 m).
- [x] **C22 [Bug] (bloquant)** `station_id` manque dans `TemperatureReport`, alors que `TemperatureReportDao` le passe au constructeur. La lecture des relevés lève donc `TypeError` (vérifié). Fichiers : [temperature_report.py:15](../api/src/business_object/temperature_report.py#L15), [temperature_report_dao.py:43](../api/src/dao/temperature_report_dao.py#L43).
- [x] **C23 [Bug]** `daily_mean()` renvoie `temp_mean` au lieu de (`temp_min` + `temp_max`) / 2. Il faut aussi retirer l'attribut `temp_mean`, y compris dans `apply_altitude_correction()` ([temperature_report.py:20-29](../api/src/business_object/temperature_report.py#L20-L29)).

### Calcul des DJU ([dju.py](../api/src/business_object/dju.py))

- [x] `DjuType` : `name`, `base_temperature`, `mode`, `compute_daily_value()` (moyenne (Tmin + Tmax) / 2), `is_heating()` et `is_cooling()`.
- [x] `DjuCalculation` :
  - attributs `start_date`, `end_date`, `time_step`, `latitude`, `longitude` et `computed_at` ;
  - associations `type`, `zone`, `candidate_stations` et `results` ;
  - `aggregate()` par jour, par mois et par année.
- [x] **C24 [Feature]** Ajouter les attributs `altitude`, `number_of_stations` et `use_altitude`.
- [x] **C25 [Bug]** `run()` ne prend pas de paramètre et n'utilise que la station la plus proche ([dju.py:150](../api/src/business_object/dju.py#L150)). Le diagramme demande `run(daily_temperatures)`, qui reçoit les températures estimées par `TemperatureService`.
- [x] **C26 [Feature]** `run_for_zone(temperatures_by_municipality)` n'existe pas. Le code actuel fait une moyenne simple des communes, chacune avec sa seule station la plus proche ([dju.py:139](../api/src/business_object/dju.py#L139)). Le diagramme demande une moyenne pondérée par la population. Comme `population` peut valoir `NULL`, il faut décider du poids d'une commune sans population (proposition : l'exclure).
- [x] **C27 [Feature]** Le pas de temps `week` est refusé : il manque dans `_VALID_TIME_STEPS` ([dju.py:17](../api/src/business_object/dju.py#L17)), dans `_period_key()` et dans `TimeStep` ([dju_schema.py:10](../api/src/schema/dju_schema.py#L10)). Proposition : semaine ISO, du lundi au dimanche.
- [x] **C28 [Bug]** `aggregate()` prend comme bornes le premier et le dernier jour **qui ont une valeur**. Le diagramme associe pourtant chaque `DjuResult` aux « bornes de période ». Il faut prendre les bornes du calendrier (début et fin de la semaine, du mois, de l'année, ramenées à la période demandée).
- [x] **C29 [Nettoyage]** Retirer `DjuCalculation.owner` et `can_reuse_intermediate()`.
- [x] `DjuResult` : `period_start`, `period_end` et `value`.
- [x] **C30 [Nettoyage]** Retirer `DjuResult.merge()`.

### Schémas (liste « Éléments faux » du diagramme de classes)

- [x] `DjuPointRequest` contient tous les paramètres de F1 (le pas de temps `week` relève de C27).
- [x] **C31 [Bug]** `ZoningCreateRequest` n'a pas de champ `name` ([zone_schema.py:26](../api/src/schema/zone_schema.py#L26)).
- [x] **C32 [Feature]** `DjuZoneRequest` n'a ni `aggregation_level` ni `use_altitude` ([dju_schema.py:34](../api/src/schema/dju_schema.py#L34)).
- [x] **C33 [Feature]** `DjuResponse` ne distingue pas les sous-zones ([dju_schema.py:56](../api/src/schema/dju_schema.py#L56)).

### Principe d'architecture

- [x] « Les objets métier n'accèdent jamais à la base de données » : c'est vrai dans le code actuel. Seules les DAO importent `DBConnection`.

---

## 2. Modèle de données

### Tables ([init_db.sql](../data/init_db.sql))

| Table | État |
|---|---|
| `users` | ✅ (le hash bcrypt est enregistré par `UserDao.create`) |
| `regions`, `departments`, `municipalities` | ✅ structure, ❌ tables vides (M6, M7) |
| `zonings`, `zoning_municipalities` | ✅ (`ON DELETE CASCADE` en place) |
| `meteo_stations` | ✅ |
| `temperature_reports` | 🟠 M1 |
| `municipality_temperatures` | ❌ M2 |
| `dju_types` | ✅ (l'unicité de `mode` et `base_temperature` a été ajoutée depuis le diagramme) |
| `dju_calculations` | 🟠 M3 |
| `dju_results` | ✅ (`ON DELETE CASCADE` en place) |

- [x] **M1 [Bug]** `temperature_reports` contient encore `temp_mean`, et n'a pas les colonnes `source_tmin` et `source_tmax` ([init_db.sql:54-62](../data/init_db.sql#L54-L62)). L'unicité de (`station_id`, `date`) et l'index sont bien en place.
- [x] **M2 [Feature]** Créer la table `municipality_temperatures`, avec la clé (`municipality_id`, `date`) et les colonnes `temp_min` et `temp_max`.
- [x] **M3 [Bug]** `dju_calculations` contient encore `latitude`, `longitude` et `user_id` ([init_db.sql:83-86](../data/init_db.sql#L83-L86)). Les colonnes `number_of_stations` et `use_altitude` sont bien présentes.
- [x] **M4 [Nettoyage]** Supprimer les tables en double `communes` et `meteo_observations` ([init_db.sql:101-129](../data/init_db.sql#L101-L129)).

### Origine des données (chaîne de scripts F0)

- [x] `init_db.py` télécharge les relevés, filtre à partir de 1990 et écrit le Parquet brut.
- [x] **M5 [Feature]** [qualite_meteo.py](../data/qualite_meteo.py#L401) n'enregistre pas le Parquet nettoyé.
- [x] **M6 [Feature]** [communes.py](../data/communes.py#L10) ne récupère ni le code INSEE (`code`), ni la population, ni les noms des départements et des régions.
- [x] **M7 [Bug] (bloquant)** [fonction_utiles.py](../data/fonction_utiles.py#L173) retélécharge tout avec `fetch_communes()` et `fetch_meteo_data()` au lieu de lire les Parquet. Il remplit aussi `communes` et `meteo_observations` au lieu des tables suivantes, dans cet ordre : `regions` → `departments` → `municipalities` → `meteo_stations` → `temperature_reports` (avec `source_*`).
- [x] **M8 [Nettoyage]** Supprimer [meteo_stations.py](../data/meteo_stations.py) une fois M7 corrigé. Ce script filtre d'ailleurs à partir de 2000, et non de 1990.

### Accès aux données (DAO)

- [x] `UserDao` est complet.
- [x] `DjuDao` est complet : `get_or_create_dju_type`, `find_calculation` (avec la clé de cache entière), `get_calculation_results`, `save_calculation` et `delete_calculations_for_zone`. Le diagramme le dit vide : ce n'est plus le cas.
- [x] `MeteoStationDao` lit les stations et trouve les N plus proches.
- [x] **M9 [Feature]** `GeoZoneDao` ne lit que des communes (par code INSEE ou par département). Il manque :
  - la lecture des régions, des départements et d'une zone par son id ;
  - la lecture d'un zonage (par id et par utilisateur), sa création (`zonings` et `zoning_municipalities`), sa mise à jour et sa suppression.
- [x] **M10 [Bug]** `TemperatureReportDao` lit `temp_mean` et passe `station_id` (lié à C22 et M1). Il faudrait aussi lire plusieurs stations en une seule requête.
- [x] **M11 [Feature]** Ajouter une DAO pour `municipality_temperatures` (lecture et insertion).
- [x] **M12 [Feature]** Le diagramme prévoit que la liste des stations est « chargée une seule fois en mémoire au démarrage ». Aujourd'hui, `find_nearest_stations()` relit toute la table à chaque appel ([meteo_station_dao.py:100](../api/src/dao/meteo_station_dao.py#L100)).

### Cache (choix du modèle de données)

- [x] **M13 [Feature]** Brancher `DjuDao` dans `calculate_zone_dju` : chercher d'abord, puis enregistrer **un calcul par sous-zone**.
- [x] **M14 [Feature]** Après une modification ou une suppression de zonage, appeler `delete_calculations_for_zone`. La méthode existe, mais rien ne l'appelle.
- [x] **M15 [Feature]** N'utiliser `municipality_temperatures` qu'avec les paramètres par défaut (3 stations et correction d'altitude). Avec d'autres paramètres, calculer sans stocker.
- [x] **M16 [Feature]** Indiquer à l'utilisateur la part de valeurs réellement observées, grâce aux colonnes `source_tmin` et `source_tmax`.

---

## 3. Diagrammes de séquence

### 1. Initialisation des données (F0)

| Étape | État | Renvoi |
|---|---|---|
| `init_db.py` → Parquet brut | ✅ | |
| `qualite_meteo.py` → Parquet nettoyé | ❌ | M5 |
| `communes.py` → Parquet des communes | 🟠 incomplet | M6 |
| `fonction_utiles.py` lit les Parquet et remplit la base | ❌ | M7 |

### 2. Calcul d'un DJU ponctuel (F1)

| Étape | État | Renvoi |
|---|---|---|
| `POST /dju/point` | ✅ route enregistrée | |
| 422 si les paramètres sont invalides | ✅ vérifié | |
| 400 si aucun seuil ou si les dates sont incohérentes | ❌ | C1 |
| `calculate_point_dju(request)` | 🟠 501, paramètre `user` en trop | C1 |
| `TemperatureService` estime les températures du point | ❌ | C4 |
| La DAO lit les relevés des stations proches | ❌ plante | C22, M10 |
| Boucle sur les seuils, `run(températures)` | ❌ | C25 |
| 200 `DjuResponse` | ✅ schéma | |

Liste « Éléments faux » de ce diagramme : `dependencies.py` existe maintenant ✅. Les autres points sont toujours d'actualité (C1, C4, C22, C25, C27).

### 3. Consultation des zonages officiels (F2)

| Étape | État | Renvoi |
|---|---|---|
| `GET /zones?type=…` | ✅ route enregistrée (corrigé depuis le diagramme) | |
| 422 si le type est inconnu | ✅ vérifié | |
| `list_public_zones(zone_type)` | 🟠 501 | C5 |
| La DAO lit les régions et les départements | ❌ | M9 |
| 200 `list[ZoneResponse]` | ✅ schéma, à alléger | D3 |

### 4. Calcul d'un DJU sur un territoire (F3)

| Étape | État | Renvoi |
|---|---|---|
| `POST /dju/zone` | ✅ route enregistrée | |
| `calculate_zone_dju(request, user)` | 🟠 501 | C2 |
| Chargement et découpage de la zone | ❌ | C7, C8 |
| Contrôle du propriétaire (401, 403, 404) | ❌ | C18, C7 |
| Recherche d'un calcul déjà stocké | 🟠 DAO prête, jamais appelée | M13 |
| Températures de chaque commune (relues ou estimées) | ❌ | C4, M2, M11 |
| `run_for_zone(températures)` | ❌ | C26 |
| Enregistrement du calcul | 🟠 DAO prête, jamais appelée | M13 |
| `DjuResponse` par sous-zone | ❌ | C33 |
| `aggregation_level` et `use_altitude` dans la requête | ❌ | C32 |
| « Ensemble de régions » | Tranché : par un zonage personnalisé | D2 |

### 5. Connexion d'un utilisateur

| Étape | État | Renvoi |
|---|---|---|
| `POST /user/login` et `POST /user/register` | ✅ routes enregistrées (corrigé depuis le diagramme) | |
| `authenticate(username, password)` | 🟠 501 | C13 |
| `UserDao.find_by_username()` | ✅ | |
| `User.check_password()` | ✅ | |
| Jeton d'accès (`TokenResponse`) | ❌ | C13, D1 |
| 401 si le mot de passe est faux | ❌ | C13 |
| 409 si le nom est pris à l'inscription | ❌ (`UserDao.create` renvoie bien `None` dans ce cas) | C13 |
| `dependencies.py` (`get_current_user`, traduction des erreurs) | ✅ existe maintenant | |

### 6. Création d'un zonage personnalisé (F4, FO3)

| Étape | État | Renvoi |
|---|---|---|
| `POST /user/zones` | ✅ route enregistrée | |
| `POST /user/zones/import` | 🟠 route existante, mais avec un upload multipart qui empêche l'API de démarrer : à remplacer par un corps JSON | H1, H11 |
| `create_zoning(user, name, description, codes_insee)` | 🟠 501, sans `name` | C9, C31 |
| Recherche des communes par code INSEE | ✅ `get_municipality_by_insee` (une requête par code) | |
| 400 si un code INSEE est inconnu | ❌ | C9 |
| `User.create_zoning(name, description)` | ❌ sans `name` | C19 |
| Enregistrement (`zonings` et `zoning_municipalities`) | ❌ | M9 |
| 201 `ZoningResponse` | ✅ schéma | |
| `import_zoning()` lit les codes du fichier | ❌ | C10 |

### 7. Modification ou suppression d'un zonage personnalisé (F4)

| Étape | État | Renvoi |
|---|---|---|
| `PATCH` et `DELETE /user/zones/{zoning_id}` | ✅ routes enregistrées | |
| `update_zoning(...)` et `delete_zoning(...)` | 🟠 501 | C11, C12 |
| La DAO lit le zonage | ❌ | M9 |
| 403 si l'utilisateur n'est pas le propriétaire, 404 si le zonage n'existe pas | ❌ | C18 |
| La DAO modifie ou supprime le zonage | ❌ | M9 |
| Suppression des calculs stockés | 🟠 DAO prête, jamais appelée | M14 |
| 200 ou 204 | ✅ contrôleur | |

---

## 4. Diagrammes d'activité

### 1. Initialisation des données (F0)

| Action | État | Renvoi |
|---|---|---|
| `telecharger_departement(dept)` avec suppression des doublons | ✅ | |
| `filtrer_donnees_meteo(chemin_gz)` | 🟠 garde encore `TM` et `TNTXM` | A1 |
| Parquet brut | ✅ | |
| Trou de 30 jours au plus : valeur comblée, source notée (`traiter_valeurs_manquantes`) | ✅ | |
| Trou de plus de 30 jours : valeur laissée vide (`rejetee_gap_trop_long`) | ✅ | |
| Parquet nettoyé | ❌ | M5 |
| `fetch_communes()` | 🟠 sans code INSEE ni population | M6 |
| Parquet des communes | ✅ | |
| `create_tables(conn)` | ✅ (script SQL relançable depuis H4) | H4 |
| Insertion des régions, des départements et des communes | ❌ | M7 |
| Insertion des stations et des relevés | ❌ | M7 |

- [x] **A1 [Nettoyage]** [init_db.py:41-45](../data/init_db.py#L41-L45) : ne plus garder les colonnes `TM` et `TNTXM`.

### 2. Estimation des températures d'un lieu

| Action | État | Renvoi |
|---|---|---|
| `find_candidate_stations(...)` | ❌ (`find_nearest_stations` existe, mais ne vérifie pas la période) | C4 |
| Message si aucune station n'est disponible | ❌ | A2 |
| `get_reports_by_station_and_date_range(...)` | 🟠 existe, mais plante | C22, M10 |
| `distance_to(lat, lon)` | ✅ | |
| Poids 1/distance² | ❌ | C4 |
| `apply_altitude_correction(delta_alt)` si l'altitude est fournie | ✅ méthode prête | |
| Moyenne pondérée chaque jour, sur les stations qui ont une valeur | ❌ | C4 |
| Sortie : Tmin et Tmax estimés pour chaque jour | ❌ | C4 |

- [x] **A2 [Feature]** Définir l'erreur « aucune station disponible » (une `ServiceError` avec un code HTTP à choisir, 404 ou 422).

### 3. Calcul d'un DJU ponctuel (F1)

| Action | État | Renvoi |
|---|---|---|
| 422 si le format est invalide | ✅ | |
| 400 si aucun seuil n'est fourni ou si `start_date` > `end_date` | ❌ | C1 |
| Création d'un `DjuType` par seuil | ❌ | C1 |
| Estimation des températures, une seule fois | ❌ | C4 |
| `DjuType.compute_daily_value(t_min, t_max)` | ✅ | |
| `DjuCalculation.aggregate(time_step)` | 🟠 sans `week`, bornes fausses | C27, C28 |
| Boucle sur les types de DJU | ❌ | C1 |
| `DjuResponse` | ✅ | |

### 4. Calcul d'un DJU sur un territoire (F3)

| Action | État | Renvoi |
|---|---|---|
| 422 ou 400 si les paramètres sont invalides | 🟠 422 seulement | C2 |
| `ZoneService.get_zone(zone_type, zone_id)`, 404 | ❌ | C7 |
| Zonage personnalisé : `is_owned_by(user)`, 401 ou 403 | ❌ | C18, A3 |
| `get_sub_zones(zone, aggregation_level)` | ❌ | C8 |
| Calcul déjà stocké ? Lecture du calcul | 🟠 DAO prête | M13 |
| `get_municipality_temperatures(...)` | ❌ | C4, M11 |
| `run_for_zone(...)`, moyenne pondérée par la population | ❌ | C26 |
| `aggregate(time_step)` | 🟠 | C27, C28 |
| Enregistrement du calcul | 🟠 DAO prête | M13 |
| Boucle sur les sous-zones, `DjuResponse` | ❌ | C33 |

- [x] **A3 [Feature]** `/dju/zone` utilise `get_optional_user`. C'est donc au service de renvoyer 401 lorsqu'un zonage personnalisé est demandé sans jeton.

### 5. Consultation des zonages officiels (F2)

| Action | État | Renvoi |
|---|---|---|
| Type `department`, `region` ou `all` | ✅ `ZoneTypeFilter` | |
| Autre valeur : 422 | ✅ vérifié | |
| Lecture des départements, des régions, ou des deux | ❌ | C5, M9 |
| Liste de `ZoneResponse` | ✅ schéma, à alléger | D3 |

### 6. Création ou import d'un zonage personnalisé (F4, FO3)

| Action | État | Renvoi |
|---|---|---|
| `get_current_user(token)`, 401 | 🟠 401 sans jeton ✅, 501 avec jeton | C13 |
| Codes INSEE de la requête ou extraits du fichier | 🟠 lecture de la requête ✅, fichier ❌ | C10 |
| Recherche de chaque commune par son code INSEE | ✅ DAO | |
| Tous les codes existent ? Sinon 400 | ❌ | C9 |
| `User.create_zoning(name, description)` | ❌ | C19 |
| `add_municipality(m)` | ✅ | |
| Enregistrement du zonage | ❌ | M9 |
| `ZoningResponse` (201) | ✅ | |

### 7. Modification ou suppression d'un zonage personnalisé (F4)

| Action | État | Renvoi |
|---|---|---|
| `get_current_user(token)`, 401 | 🟠 comme pour l'activité 6 | C13 |
| Chargement du zonage, 404 | ❌ | M9 |
| `is_owned_by(user)`, 403 | ❌ | C18 |
| `update_zoning(...)` ou `delete_zoning(...)` | ❌ | C11, C12 |
| Suppression des calculs stockés | 🟠 DAO prête | M14 |
| `ZoningResponse` (200) ou réponse vide (204) | ✅ | |

---

## 5. Annexe : problèmes absents des diagrammes

- [x] **H1 [Bug] (bloquant)** L'API ne démarre pas. La route d'import ([zone_controller.py:86](../api/src/controllers/zone_controller.py#L86)) utilise `UploadFile`, `File` et `Form`. FastAPI décode ce format (`multipart/form-data`) avec la bibliothèque `python-multipart`, absente de [pyproject.toml](../api/pyproject.toml#L8) : `import main` lève donc `RuntimeError`. **Correction retenue : ne pas ajouter la bibliothèque**, mais remplacer l'upload par un corps JSON (voir H11).
- [x] **H2 [Bug] (bloquant)** L'API ne charge pas le `.env`. `DBConnection` lit `os.environ["POSTGRES_*"]` ([db_connection.py:27](../api/src/dao/db_connection.py#L27)), mais rien dans `api/` n'appelle `load_dotenv()`.
- [x] **H3 [Bug]** Les chemins sont écrits en dur pour Onyxia (`/home/onyxia/work/...`) dans `init_db.py`, `communes.py` et `data_visualisation.py`, alors que `qualite_meteo.py` utilise un chemin relatif.
- [x] **H4 [Bug]** `init_db.sql` n'est pas relançable : les `CREATE TABLE` sont écrits sans `IF NOT EXISTS`.
- [x] **H5 [Nettoyage]** Les dépendances des scripts de données (`pandas`, `pyarrow`, `numpy`, `python-dotenv`, `duckdb`, `rich`) ne sont déclarées nulle part.
- [x] **H6 [Feature]** Tests :
  - `testpaths = ["tests"]` alors que le dossier s'appelle `test/` ([pyproject.toml:47](../api/pyproject.toml#L47)) ;
  - `pytest` n'est pas installé dans `.venv` ;
  - [test_dju_service.py](../api/test/test_dju_service.py) ne contient qu'un commentaire.

  Le diagramme précise que les objets métier « peuvent être testés sans base » : on peut donc commencer par `DjuType`, `aggregate`, l'IDW, la correction d'altitude, la moyenne pondérée et `Zoning`.
- [ ] **H7 [Nettoyage]** Onze fichiers `.pyc` et `.DS_Store` sont suivis par git. Par ailleurs, une modification de `main.py` n'est pas commitée : le port par défaut passe de 5000 à 5001.
  - Fait : `.gitignore` complété (`.DS_Store`, `*.pyc`, `data/raw_data/`), et `UVICORN_PORT=5001` dans le `.env`.
  - Reste à faire à la main (aucune opération git n'a été lancée) : `git rm -r --cached --ignore-unmatch '*.pyc' '.DS_Store' 'doc/.DS_Store' 'doc/reports/.DS_Store'`, puis le commit.
- [x] **H8 [Nettoyage]** [log_utils.py](../api/src/utils/log_utils.py) attend un `logging_config.yml` absent, et `LogMiddleware` n'est branché nulle part.
- [x] **H9 [Feature]** Export CSV (décision D4) : un paramètre `format=json|csv` sur `POST /dju/point` et `POST /dju/zone`, avec les colonnes `zone`, `mode`, `period_start`, `period_end` et `value`.
- [x] **H10 [Feature]** Route `GET /zones/{zone_type}/{zone_id}` pour le détail d'une zone avec ses communes, et `ZoneResponse` allégée, sans `municipalities` (décision D3, [zone_controller.py:29](../api/src/controllers/zone_controller.py#L29)).
- [x] **H11 [Bug]** Remplacer l'upload de fichier par un corps JSON (décision D5). Aujourd'hui, `import_zoning` reçoit `file: UploadFile = File(...)` et `description: str = Form(...)`. À la place :
  - créer un schéma `ZoningImportRequest` avec `name`, `description`, `filename` et `content` (le texte du fichier CSV ou JSON) ;
  - la route devient `def import_zoning(request: ZoningImportRequest, user=Depends(get_current_user))`, sans `UploadFile` ni `await file.read()` ;
  - le service lit `content` avec `csv` ou `json` de la bibliothèque standard, et choisit le format d'après l'extension de `filename` ;
  - la signature du diagramme `import_zoning(user, filename, content, description)` reste valable, avec `content` de type `str` au lieu de `bytes` (et un `name` en plus, voir Q5).

  Contrepartie : l'utilisateur colle le contenu du fichier dans le JSON au lieu de l'envoyer comme fichier. Pour une liste de codes INSEE, cela reste léger.
- [x] **H12 [Nettoyage]** Remplacer tous les `async def` par des `def` simples (décision D6). Les fonctions concernées :
  - [main.py](../api/src/main.py#L47) : `redirect_to_docs` et `health_check` ;
  - [dju_controller.py](../api/src/controllers/dju_controller.py) : `get_dju_info`, `calculate_point_dju`, `compute_zone_dju` ;
  - [user_controller.py](../api/src/controllers/user_controller.py) : `register` et `login` ;
  - [zone_controller.py](../api/src/controllers/zone_controller.py) : `list_zones`, `list_my_zonings`, `create_zoning`, `import_zoning`, `update_zoning`, `delete_zoning`.

  Raison : tout le code appelé est synchrone (`psycopg2`, `bcrypt`, les calculs). Dans un `async def`, ces appels bloquent la boucle d'événements et donc tout le serveur pendant qu'ils tournent. Avec un `def`, FastAPI exécute la route dans un thread séparé et les autres requêtes continuent d'être servies. Le seul `await` du projet est celui de l'upload (`await file.read()`), qui disparaît avec H11.

---

## 6. Mises à jour à faire dans `new_diagram.md`

*Faites le 3 novembre 2026 : les sections « Éléments faux » sont remplacées par des sections « État du code », et les diagrammes intègrent les points ci-dessous.*

1. **Retirer des listes « Éléments faux » les points déjà corrigés** :
   - `dju_dao.py` n'est plus vide ;
   - l'unicité de `dju_types` est en place ;
   - `number_of_stations` et `use_altitude` sont dans `dju_calculations` ;
   - `controllers/dependencies.py` existe ;
   - `main.py` enregistre les routeurs `/zones`, `/user` et `/user/zones` ;
   - `DjuService.calculate_point_dju()` et `calculate_zone_dju()` existent, même s'ils renvoient 501.
2. **Corriger une formulation** : `zone_service.py` et `auth_service.py` ne sont plus vides, mais leurs méthodes renvoient 501.
3. **Séquence 5** : préciser que le jeton est un JWT (D1).
4. **Séquence 4** : préciser que l'« ensemble de régions » passe par un zonage personnalisé (D2).
5. **Séquence et activité F2** : ajouter la liste allégée et la route de détail (D3).
6. **Diagramme de classes** : garder `zone_type`. Le diagramme le retire (« le type est donné par la sous-classe »), mais `DjuDao.save_calculation()` et le contrôleur l'utilisent. Il faut le réintégrer comme constante de classe.
7. **Séquences F1 et F3** : ajouter la sortie CSV (D4).
8. **Séquence 6** : préciser que l'import envoie le contenu du fichier dans un corps JSON, et non un fichier uploadé (D5).

---

## 7. Décisions et questions

**Décisions prises (3 novembre 2026)**
- **D1** : authentification par jeton JWT signé (`pyjwt`), sans table de jetons.
- **D2** : un « ensemble de régions » passe par un zonage personnalisé ; `DjuZoneRequest` garde un seul `zone_id`.
- **D3** : `GET /zones` renvoie une liste légère, et le détail est sur `GET /zones/{zone_type}/{zone_id}`.
- **D4** : l'export CSV est prévu en option, avec le module `csv` de la bibliothèque standard.
- **D5** : pas d'upload `multipart/form-data` ; l'import d'un zonage passe par un corps JSON (H11). La bibliothèque `python-multipart` n'est donc pas ajoutée.
- **D6** : routes en `def` simples, sans programmation asynchrone (H12).
- **Principe** : privilégier la bibliothèque standard et les dépendances déjà déclarées dans [pyproject.toml](../api/pyproject.toml) avant d'en ajouter de nouvelles.

**Questions encore ouvertes**
- **Q7 : bibliothèque pour le JWT.** La décision D1 (JWT) demande `pyjwt`, ce qui contredit le principe ci-dessus. Deux options : garder `pyjwt` (une bibliothèque très courante, qui gère la signature et l'expiration), ou signer le jeton soi-même avec `hmac`, `hashlib`, `base64` et `json` de la bibliothèque standard (environ 30 lignes, mais du code de sécurité à maintenir et à tester). Je recommande `pyjwt`.
- **Q5 : nom d'un zonage importé.** La signature `import_zoning(user, filename, content, description)` du diagramme n'a pas de nom. Proposition : un champ `name` facultatif, avec le nom du fichier par défaut.
- **Q6 : outre-mer.** `init_db.py` télécharge aussi les départements 971 à 988 et 99. Les gardons-nous dans le périmètre ?

---

## 8. Ordre de travail proposé

1. **Débloquer** : H1 (par H11), H12, H2, C22, C23, M10.
2. **Données (F0)** : M6 → M5 → M1, M2, M3, M4 → M7 → M8.
3. **F1** : C4, C24, C25, C27, C28, puis C1 et A2, avec des tests (H6).
4. **F2** : M9 (lecture), C5, puis H10.
5. **F3 et FO1** : C7, C8, C26, C32, C33, M11, M12, M13, M15, puis C2 et A3.
6. **Authentification et F4** : C13 (JWT), C18, C19, C31, M9 (écriture), C6, C9, C11, C12, M14, puis **FO3** (C10).
7. **Finitions** : H9 (CSV), nettoyage (C3, C14 à C17, C20, C21, C29, C30, A1, H3 à H8), puis les mises à jour de la section 6.
