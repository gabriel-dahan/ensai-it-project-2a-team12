-- Schéma de la base, exécuté par data/init_db.py.
-- IF NOT EXISTS : on peut relancer le script sans effacer les tables ni leurs données.

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS regions (
    id SERIAL PRIMARY KEY,
    insee_code VARCHAR(5) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS departments (
    id SERIAL PRIMARY KEY,
    insee_code VARCHAR(5) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    region_id INTEGER NOT NULL REFERENCES regions (id)
);

CREATE TABLE IF NOT EXISTS municipalities (
    id SERIAL PRIMARY KEY,
    insee_code VARCHAR(5) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    altitude DOUBLE PRECISION,
    population INTEGER,
    department_id INTEGER NOT NULL REFERENCES departments (id)
);

CREATE INDEX IF NOT EXISTS idx_municipalities_department
    ON municipalities (department_id);

CREATE TABLE IF NOT EXISTS zonings (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at DATE NOT NULL DEFAULT CURRENT_DATE,
    user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS zoning_municipalities (
    zoning_id INTEGER NOT NULL REFERENCES zonings (id) ON DELETE CASCADE,
    municipality_id INTEGER NOT NULL REFERENCES municipalities (id),
    PRIMARY KEY (zoning_id, municipality_id)
);

CREATE TABLE IF NOT EXISTS meteo_stations (
    id SERIAL PRIMARY KEY,
    station_code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(255),
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    altitude DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS temperature_reports (
    id BIGSERIAL PRIMARY KEY,
    station_id INTEGER NOT NULL REFERENCES meteo_stations (id),
    date DATE NOT NULL,
    temp_min DOUBLE PRECISION,
    temp_max DOUBLE PRECISION,
    source_tmin VARCHAR(32),
    source_tmax VARCHAR(32),
    UNIQUE (station_id, date)
);

CREATE TABLE IF NOT EXISTS dju_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    mode VARCHAR(16) NOT NULL CHECK (mode IN ('heating', 'cooling')),
    base_temperature DOUBLE PRECISION NOT NULL,
    UNIQUE (mode, base_temperature)
);

CREATE TABLE IF NOT EXISTS dju_calculations (
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

CREATE INDEX IF NOT EXISTS idx_dju_calculations_zone
    ON dju_calculations (zone_type, zone_id);

CREATE TABLE IF NOT EXISTS dju_results (
    id SERIAL PRIMARY KEY,
    calculation_id INTEGER NOT NULL REFERENCES dju_calculations (id) ON DELETE CASCADE,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    days_with_data INTEGER NOT NULL,
    observed_ratio DOUBLE PRECISION NOT NULL
);
