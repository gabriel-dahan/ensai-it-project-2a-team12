DROP TABLE IF EXISTS meteo_observations CASCADE;
DROP TABLE IF EXISTS communes CASCADE;

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
