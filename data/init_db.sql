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
    user_id INTEGER NOT NULL REFERENCES users (id)
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

CREATE TABLE temperature_reports (
    id BIGSERIAL PRIMARY KEY,
    station_id INTEGER NOT NULL REFERENCES meteo_stations (id),
    date DATE NOT NULL,
    temp_min DOUBLE PRECISION,
    temp_max DOUBLE PRECISION,
    temp_mean DOUBLE PRECISION,
    UNIQUE (station_id, date)
);

CREATE INDEX idx_temperature_reports_station_date
    ON temperature_reports (station_id, date);

CREATE TABLE dju_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    base_temperature DOUBLE PRECISION NOT NULL,
    mode VARCHAR(16) NOT NULL CHECK (mode IN ('heating', 'cooling'))
);

CREATE TABLE dju_calculations (
    id SERIAL PRIMARY KEY,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    time_step VARCHAR(16) NOT NULL,
    computed_at DATE,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    dju_type_id INTEGER NOT NULL REFERENCES dju_types (id),
    user_id INTEGER REFERENCES users (id),
    zone_type VARCHAR(32),
    zone_id INTEGER
);

CREATE TABLE dju_results (
    id SERIAL PRIMARY KEY,
    calculation_id INTEGER NOT NULL REFERENCES dju_calculations (id) ON DELETE CASCADE,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    value DOUBLE PRECISION NOT NULL
);

-- Open-data tables filled by data/fonction_utiles.py.

CREATE TABLE communes (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(255),
    code_postal VARCHAR(10),
    code_departement VARCHAR(5),
    code_region VARCHAR(5),
    longitude FLOAT,
    latitude FLOAT,
    altitude FLOAT
);

CREATE TABLE meteo_observations (
    id BIGSERIAL PRIMARY KEY,
    num_poste VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    nom_usuel VARCHAR(255),
    tmin FLOAT,
    tmax FLOAT,
    tmean FLOAT,
    latitude FLOAT,
    longitude FLOAT,
    altitude FLOAT,
    tmed_tn_tx FLOAT
);

CREATE INDEX idx_meteo_observations_poste_date
    ON meteo_observations (num_poste, date);
