# Sequence diagrams

These diagrams describe the main exchanges between the client, the API layers
(controller, service, DAO) and the database. They follow the layered
architecture of the project and cover the features F0 to F4, plus the optional
import of custom zonings (FO3).

## 1. Initialize the databases (F0)

The administrator loads Météo-France temperature records and the municipality
referential (data.gouv.fr / geo.api.gouv.fr), then persists stations, daily
reports and official zonings (municipality, department, region).

```mermaid
sequenceDiagram
    actor Admin
    participant Init as Init scripts
    participant Meteo as Météo-France / data.gouv.fr
    participant Geo as geo.api.gouv.fr
    participant Alti as Altimetry API
    participant DAO as DAO layer
    participant DB as Database

    Admin->>Init: Start database initialization

    rect rgb(240, 248, 255)
        Note over Init,DB: Weather data
        loop For each department
            Init->>Meteo: Download daily temperature file (.csv.gz)
            Meteo-->>Init: Compressed SYNOP records
            Init->>Init: Filter columns, keep dates from 1990,<br/>deduplicate (station, date)
        end
        Init->>DAO: save_stations_and_reports(data)
        DAO->>DB: INSERT meteo_station, temperature_report
        DB-->>DAO: ok
    end

    rect rgb(245, 255, 245)
        Note over Init,DB: Geographic referential
        Init->>Geo: GET /communes (name, centre, department, region)
        Geo-->>Init: list of municipalities
        loop Batches of municipalities
            Init->>Alti: GET elevations(lon, lat)
            Alti-->>Init: altitude
        end
        Init->>DAO: save_zones(municipalities, departments, regions)
        DAO->>DB: INSERT municipality, department, region and links
        DB-->>DAO: ok
    end

    Init-->>Admin: Databases ready
```

## 2. Compute a punctual DJU (F1)

An anonymous or authenticated client requests heating / cooling DJU for GPS
coordinates, over a period and a time step (daily, weekly, monthly, yearly).
Cached results are reused when available (FO1). Otherwise temperatures are
estimated from nearby stations (inverse distance weighting, optional altitude
correction).

```mermaid
sequenceDiagram
    actor Client
    participant Controller as DjuController
    participant DjuSvc as DjuService
    participant TempSvc as TemperatureService
    participant StationDao as MeteoStationDao
    participant ReportDao as TemperatureReportDao
    participant DjuDao as DjuDao
    participant DB as Database

    Client->>Controller: POST /dju/point<br/>(lat, lon, period, thresholds, time step, n stations)
    Controller->>Controller: Validate request (DjuPointRequest)

    alt Invalid parameters
        Controller-->>Client: 400 Bad Request
    else Valid request
        Controller->>DjuSvc: calculate_point_dju(params)

        DjuSvc->>DjuDao: find_reusable_result(params)
        DjuDao->>DB: SELECT cached DJU
        DB-->>DjuDao: existing result or none
        DjuDao-->>DjuSvc: cached result?

        alt Cached result available
            DjuSvc-->>Controller: list[DjuResult]
        else Compute from meteorological data
            DjuSvc->>TempSvc: estimate_temperatures(lat, lon, period, n)
            TempSvc->>StationDao: get_nearby_stations(lat, lon, n)
            StationDao->>DB: SELECT nearest stations (Haversine)
            DB-->>StationDao: stations
            StationDao-->>TempSvc: list[MeteoStation]

            TempSvc->>ReportDao: get_reports(stations, start, end)
            ReportDao->>DB: SELECT temperature reports
            DB-->>ReportDao: reports
            ReportDao-->>TempSvc: list[TemperatureReport]

            TempSvc->>TempSvc: IDW interpolation + altitude correction
            TempSvc-->>DjuSvc: daily temperatures

            DjuSvc->>DjuSvc: Compute daily heating / cooling DJU
            DjuSvc->>DjuSvc: Aggregate by time step

            DjuSvc->>DjuDao: save(DjuCalculation)
            DjuDao->>DB: INSERT results
            DB-->>DjuDao: ok
            DjuDao-->>DjuSvc: saved

            DjuSvc-->>Controller: list[DjuResult]
        end

        Controller-->>Client: JSON response
    end
```

## 3. Consult public zonings (F2)

Any client can list official geographic zones (departments and regions) and
their municipalities. These zonings are available to every user.

```mermaid
sequenceDiagram
    actor Client
    participant Controller as ZoneController
    participant ZoneSvc as ZoneService
    participant ZoneDao as GeoZoneDao
    participant DB as Database

    Client->>Controller: GET /zones?type=department|region
    Controller->>ZoneSvc: list_public_zones(zone_type)
    ZoneSvc->>ZoneDao: find_by_type(zone_type)
    ZoneDao->>DB: SELECT zones and municipalities
    DB-->>ZoneDao: zone rows
    ZoneDao-->>ZoneSvc: list[GeographicZone]
    ZoneSvc-->>Controller: departments or regions
    Controller-->>Client: JSON list of public zonings
```

## 4. Compute a zone DJU (F3)

DJU are computed on a territory (department, region, or custom zoning) with a
given period, time step and granularity. For official zonings the client does
not need to be authenticated. For a personal zoning, authentication is
required. Municipality-level DJU are then aggregated (for example
population-weighted).

```mermaid
sequenceDiagram
    actor Client
    participant Controller as DjuController
    participant AuthSvc as AuthService
    participant DjuSvc as DjuService
    participant ZoneSvc as ZoneService
    participant ZoneDao as GeoZoneDao
    participant DjuDao as DjuDao
    participant DB as Database

    Client->>Controller: POST /dju/zone<br/>(zone id, period, thresholds, time step)
    Controller->>Controller: Validate request

    alt Invalid parameters
        Controller-->>Client: 400 Bad Request
    else Valid request
        Controller->>ZoneSvc: get_zone(zone_id)
        ZoneSvc->>ZoneDao: find_zone(zone_id)
        ZoneDao->>DB: SELECT zone and municipalities
        DB-->>ZoneDao: zone data
        ZoneDao-->>ZoneSvc: GeographicZone
        ZoneSvc-->>Controller: zone

        alt Zone not found
            Controller-->>Client: 404 Not Found
        else Custom zoning: authentication required
            Controller->>AuthSvc: authenticate(credentials)
            alt Authentication failed or not the owner
                AuthSvc-->>Controller: rejected
                Controller-->>Client: 401 / 403
            else Authenticated owner
                AuthSvc-->>Controller: User
            end
        else Public zone (department or region)
            Note over Controller: No authentication required
        end

        Controller->>DjuSvc: calculate_zone_dju(zone, params)

        DjuSvc->>DjuDao: find_reusable_result(zone, params)
        DjuDao->>DB: SELECT cached DJU
        DB-->>DjuDao: existing result or none
        DjuDao-->>DjuSvc: cached result?

        alt Cached result available
            DjuSvc-->>Controller: list[DjuResult]
        else Compute from municipalities
            DjuSvc->>ZoneSvc: get_municipalities(zone)
            ZoneSvc-->>DjuSvc: list[Municipality]

            loop For each municipality
                DjuSvc->>DjuSvc: calculate_point_dju(municipality coordinates)
            end

            DjuSvc->>DjuSvc: Aggregate municipality results<br/>(e.g. population-weighted)
            DjuSvc->>DjuDao: save(DjuCalculation)
            DjuDao->>DB: INSERT results
            DB-->>DjuDao: ok

            DjuSvc-->>Controller: list[DjuResult]
        end

        Controller-->>Client: JSON response
    end
```

## 5. Authenticate a user

Authentication is required before creating, importing or managing personal
zonings (F4).

```mermaid
sequenceDiagram
    actor User
    participant Controller as UserController
    participant AuthSvc as AuthService
    participant UserDao as UserDao
    participant DB as Database

    User->>Controller: POST /user/login (username, password)
    Controller->>AuthSvc: authenticate(credentials)
    AuthSvc->>UserDao: find_by_username(username)
    UserDao->>DB: SELECT user
    DB-->>UserDao: user row or none
    UserDao-->>AuthSvc: User?

    alt Unknown user or invalid password
        AuthSvc-->>Controller: rejected
        Controller-->>User: 401 Unauthorized
    else Valid credentials
        AuthSvc->>AuthSvc: Issue session / token
        AuthSvc-->>Controller: authenticated User
        Controller-->>User: 200 OK (session)
    end
```

## 6. Create a personalized zoning (F4)

An authenticated user builds a custom territory as a set of municipalities and
stores it for later DJU calculations.

```mermaid
sequenceDiagram
    actor User
    participant Controller as ZoneController
    participant AuthSvc as AuthService
    participant ZoneSvc as ZoneService
    participant ZoneDao as GeoZoneDao
    participant DB as Database

    User->>Controller: POST /user/zones (description, municipalities)
    Controller->>AuthSvc: authenticate(credentials)
    AuthSvc-->>Controller: authenticated User?

    alt Authentication failed
        Controller-->>User: 401 Unauthorized
    else User is authenticated
        Controller->>ZoneSvc: create_zoning(user, description, municipalities)
        ZoneSvc->>ZoneSvc: Validate that municipalities exist
        alt Invalid municipalities
            ZoneSvc-->>Controller: error
            Controller-->>User: 400 Bad Request
        else Valid zoning
            ZoneSvc->>ZoneDao: save(Zoning)
            ZoneDao->>DB: INSERT zoning and municipality links
            DB-->>ZoneDao: zoning id
            ZoneDao-->>ZoneSvc: Zoning
            ZoneSvc-->>Controller: Zoning
            Controller-->>User: 201 Created zoning
        end
    end
```

## 7. Manage a personalized zoning (F4)

The owner can update the description, add or remove municipalities, or delete
a personal zoning.

```mermaid
sequenceDiagram
    actor User
    participant Controller as ZoneController
    participant AuthSvc as AuthService
    participant ZoneSvc as ZoneService
    participant ZoneDao as GeoZoneDao
    participant DB as Database

    User->>Controller: PATCH / DELETE /user/zones/{id}
    Controller->>AuthSvc: authenticate(credentials)
    AuthSvc-->>Controller: User

    alt Authentication failed
        Controller-->>User: 401 Unauthorized
    else Authenticated
        Controller->>ZoneSvc: get_zoning(id)
        ZoneSvc->>ZoneDao: find_zone(id)
        ZoneDao->>DB: SELECT zoning
        DB-->>ZoneDao: zoning
        ZoneDao-->>ZoneSvc: Zoning

        alt Zoning not found or not owned by user
            ZoneSvc-->>Controller: forbidden
            Controller-->>User: 404 / 403
        else Update zoning
            ZoneSvc->>ZoneDao: update(Zoning)
            ZoneDao->>DB: UPDATE zoning / links
            DB-->>ZoneDao: ok
            ZoneSvc-->>Controller: updated Zoning
            Controller-->>User: 200 OK
        else Delete zoning
            ZoneSvc->>ZoneDao: delete(id)
            ZoneDao->>DB: DELETE zoning
            DB-->>ZoneDao: ok
            ZoneSvc-->>Controller: deleted
            Controller-->>User: 204 No Content
        end
    end
```

## 8. Import a zoning from a file (FO3)

An authenticated user uploads a CSV or JSON file listing municipalities. The
API parses the file, maps rows to known communes, then stores a personal
zoning (same persistence path as F4).

```mermaid
sequenceDiagram
    actor User
    participant Controller as ZoneController
    participant AuthSvc as AuthService
    participant ZoneSvc as ZoneService
    participant ZoneDao as GeoZoneDao
    participant DB as Database

    User->>Controller: POST /user/zones/import (CSV or JSON file)
    Controller->>AuthSvc: authenticate(credentials)
    AuthSvc-->>Controller: authenticated User?

    alt Authentication failed
        Controller-->>User: 401 Unauthorized
    else User is authenticated
        Controller->>ZoneSvc: import_zoning(user, file)
        ZoneSvc->>ZoneSvc: Parse file and resolve municipalities

        alt Invalid format or unknown communes
            ZoneSvc-->>Controller: error
            Controller-->>User: 400 Bad Request
        else Valid file
            ZoneSvc->>ZoneDao: save(Zoning)
            ZoneDao->>DB: INSERT zoning and municipality links
            DB-->>ZoneDao: zoning id
            ZoneDao-->>ZoneSvc: Zoning
            ZoneSvc-->>Controller: Zoning
            Controller-->>User: 201 Created zoning
        end
    end
```
