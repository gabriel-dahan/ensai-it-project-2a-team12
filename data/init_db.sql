-- Schéma de la base, conforme au modèle de données de doc/new_diagram.md.
-- Exécuté par data/init_db.py (F0). Les DROP réinitialisent toute la base,
-- y compris les comptes et les zonages : à lancer une seule fois, avant d'utiliser l'API.

DROP TABLE IF EXISTS
    dju_results, dju_calculations, dju_types,
    municipality_temperatures, temperature_reports, meteo_stations,
    zoning_municipalities, zonings, users,
    municipalities, departments, regions,
    communes, meteo_observations  -- anciennes tables, remplacées par les tables normalisées
CASCADE;

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL
);

CREATE TABLE regions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    insee_code VARCHAR(5) UNIQUE NOT NULL
);

CREATE TABLE departments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    insee_code VARCHAR(5) UNIQUE NOT NULL,
    region_id INTEGER NOT NULL REFERENCES regions (id)
);

CREATE TABLE municipalities (
    id SERIAL PRIMARY KEY,
    insee_code VARCHAR(5) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    altitude DOUBLE PRECISION,
    population INTEGER,
    department_id INTEGER NOT NULL REFERENCES departments (id)
);

CREATE TABLE zonings (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at DATE NOT NULL DEFAULT CURRENT_DATE,
    user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE zoning_municipalities (
    zoning_id INTEGER NOT NULL REFERENCES zonings (id) ON DELETE CASCADE,
    municipality_id INTEGER NOT NULL REFERENCES municipalities (id),
    PRIMARY KEY (zoning_id, municipality_id)
);

CREATE TABLE meteo_stations (
    id SERIAL PRIMARY KEY,
    station_code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(255),
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    altitude DOUBLE PRECISION
);

-- La contrainte UNIQUE crée aussi l'index (station_id, date) utilisé pour lire
-- les relevés d'une station sur une période.
CREATE TABLE temperature_reports (
    id BIGSERIAL PRIMARY KEY,
    station_id INTEGER NOT NULL REFERENCES meteo_stations (id),
    date DATE NOT NULL,
    temp_min DOUBLE PRECISION,
    temp_max DOUBLE PRECISION,
    source_tmin VARCHAR(30),
    source_tmax VARCHAR(30),
    UNIQUE (station_id, date)
);

-- Cache rempli par l'API : températures estimées d'une commune
-- (3 stations, correction d'altitude).
CREATE TABLE municipality_temperatures (
    municipality_id INTEGER NOT NULL REFERENCES municipalities (id),
    date DATE NOT NULL,
    temp_min DOUBLE PRECISION,
    temp_max DOUBLE PRECISION,
    PRIMARY KEY (municipality_id, date)
);

CREATE TABLE dju_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    base_temperature DOUBLE PRECISION NOT NULL,
    mode VARCHAR(16) NOT NULL CHECK (mode IN ('heating', 'cooling')),
    UNIQUE (mode, base_temperature)
);

-- zone_type vaut region, department, municipality ou zoning ; zone_id est l'id
-- dans la table correspondante (pas de clé étrangère possible).
CREATE TABLE dju_calculations (
    id SERIAL PRIMARY KEY,
    dju_type_id INTEGER NOT NULL REFERENCES dju_types (id),
    zone_type VARCHAR(32) NOT NULL,
    zone_id INTEGER NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    time_step VARCHAR(16) NOT NULL,
    number_of_stations INTEGER NOT NULL,
    use_altitude BOOLEAN NOT NULL,
    computed_at DATE
);

CREATE TABLE dju_results (
    id SERIAL PRIMARY KEY,
    calculation_id INTEGER NOT NULL REFERENCES dju_calculations (id) ON DELETE CASCADE,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    value DOUBLE PRECISION NOT NULL
);
