# DJU API

## Presentation

The objective of this project is to develop an API capable of calculating Degree Days (DJU) from meteorological data.

DJU are used to estimate the severity of the climate and are notably used to analyze energy consumption related to heating and cooling.

The application will make it possible to calculate DJU for a given geographical point or for a larger geographical area.

Main features

The project includes the following main features:

- retrieve and prepare meteorological data;
- calculate DJU for a geographical point based on its coordinates;
- calculate DJU over a given period;
- allow different time steps: daily, weekly, monthly, yearly;
- calculate DJU for territories such as municipalities, departments, or regions;
- aggregate results from municipalities;
- take heating and cooling thresholds into account;
- reuse certain intermediate results in order to avoid unnecessary calculations.

## Data used

The meteorological data used mainly come from the daily records of Météo France weather stations available on data.gouv.fr.

These data include in particular:

- the date;
- the minimum temperature;
- the maximum temperature;
- the latitude;
- the longitude;
- the altitude of the stations.

For territorial calculations, the project also requires information related to municipalities, including:

- their coordinates;
- their altitude;
- their population.

## Temperature estimation

To calculate DJU for a location that does not directly correspond to a weather station, the temperature must be estimated using several nearby stations.

The proposed method is based on inverse distance weighting.

Distances between geographical coordinates can be calculated using the Haversine formula.

A correction related to altitude can also be applied.

## Architecture

The project is based on the ENSAI second-year computer science project template.

The application follows a layered architecture:

- business_object : dju.py, geo_zone.py, meteo_station.py, temperature_report.py, user.py
- dao : db_connection.py, dju_dao.py, geo_zone_dao.py, meteo_station_dao.py, municipality_temperature_dao.py, temperature_report_dao.py, user_dao.py, zoning_dao.py
- service : auth_service.py, dju_service.py, errors.py, temperature_service.py, zone_service.py
- controllers and schema : the API routes and the request / response formats

This organization makes it possible to separate:

- business objects;
- data access;
- business logic;
- exposure of functionalities through the API.

## Data pipeline

The scripts of the `data/` folder are run once, in this order, before using the API (see `api/README.md` for the commands):

1. `meteo.py` downloads the daily Météo-France records since 1990 and writes the raw Parquet file.
2. `qualite_meteo.py` removes the stations that only measure rainfall, fills the gaps of up to 30 days (interpolation, then nearby stations within 50 km) and writes the cleaned Parquet file. The origin of each value is kept in `SOURCE_TMIN` / `SOURCE_TMAX`.
3. `communes.py` downloads the regions, departments and municipalities (town hall coordinates, altitude, population).
4. `init_db.py` creates the tables of `init_db.sql` and fills them from the Parquet files.

`test_data.py` tests these scripts without network or database.

## Technologies

Technologies used or planned as part of the project:

- Python
- FastAPI
- database
- REST API

This section will be completed progressively as the technical choices for the project are made.

## Team 12

Project carried out as part of the second-year computer science project at ENSAI.

Team members:

- Gabriel Dahan
- Eudes Sterlin
- Marceau Feral
- Gwenael Lassalle 
- Mohamed Aziz Youssfi