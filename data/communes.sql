DROP TABLE IF EXISTS communes;

CREATE TABLE communes (
    id SERIAL PRIMARY KEY,            -- Un identifiant
    nom VARCHAR(255),                 -- Le nom de la commune
    code_postal VARCHAR(10),          -- Le code postal 
    code_departement VARCHAR(5),      -- Le département 
    code_region VARCHAR(5),           -- La région
    longitude FLOAT,                  -- Coordonnée GPS
    latitude FLOAT,                   -- Coordonnée GPS
    altitude FLOAT                    -- L'altitude 
);