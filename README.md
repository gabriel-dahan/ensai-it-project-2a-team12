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
- dao : db_connection.py, dju_dao.py, geo_zone_dao.py, meteo_station.py, temperature_report_dao.py, user_dao.py
- service
- view

This organization makes it possible to separate:

- business objects;
- data access;
- business logic;
- exposure of functionalities through the API.

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