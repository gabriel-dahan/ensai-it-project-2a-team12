# Sequence diagrams

## 1. Compute a punctual DJU

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

    Client->>Controller: POST /dju/point<br/>(lat, lon, period, thresholds, time step)
    Controller->>Controller: Validate request (DjuPointRequest)
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
        StationDao->>DB: SELECT nearest stations
        DB-->>StationDao: stations
        StationDao-->>TempSvc: list[MeteoStation]

        TempSvc->>ReportDao: get_reports(stations, start, end)
        ReportDao->>DB: SELECT temperature reports
        DB-->>ReportDao: reports
        ReportDao-->>TempSvc: list[TemperatureReport]

        TempSvc->>TempSvc: Inverse distance weighting<br/>and altitude correction
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
```





## 2. Compute a zone DJU

Anonymous users can request DJU for an administrative territory (municipality, department, region) or a stored zoning. The zone is expanded into municipalities, then results are aggregated (for example with a population-weighted average).

```mermaid
sequenceDiagram
    actor Client
    participant Controller as DjuController
    participant DjuSvc as DjuService
    participant ZoneSvc as ZoneService
    participant ZoneDao as GeoZoneDao
    participant DjuDao as DjuDao
    participant DB as Database

    Client->>Controller: POST /dju/zone<br/>(zone id, period, thresholds, time step)
    Controller->>Controller: Validate request
    Controller->>DjuSvc: calculate_zone_dju(params)

    DjuSvc->>ZoneSvc: get_municipalities(zone_id)
    ZoneSvc->>ZoneDao: find_zone(zone_id)
    ZoneDao->>DB: SELECT zone and municipalities
    DB-->>ZoneDao: zone data
    ZoneDao-->>ZoneSvc: GeographicZone
    ZoneSvc-->>DjuSvc: list[Municipality]

    loop For each municipality
        DjuSvc->>DjuSvc: calculate_point_dju(municipality coordinates)
    end

    DjuSvc->>DjuSvc: Aggregate municipality results<br/>(e.g. population-weighted)
    DjuSvc->>DjuDao: save(DjuCalculation)
    DjuDao->>DB: INSERT results
    DB-->>DjuDao: ok

    DjuSvc-->>Controller: list[DjuResult]
    Controller-->>Client: JSON response
```





## 3. Create a personalized zoning

Authenticated users can build a custom zoning from municipalities. Importing a zoning is an extension of this flow.

```mermaid
sequenceDiagram
    actor User
    participant Controller as ZoneController
    participant AuthSvc as AuthService
    participant ZoneSvc as ZoneService
    participant ZoneDao as GeoZoneDao
    participant DB as Database

    User->>Controller: POST /zones (description, municipalities)
    Controller->>AuthSvc: authenticate(credentials)
    AuthSvc-->>Controller: authenticated User

    alt Authentication failed
        Controller-->>User: 401 Unauthorized
    else User is authenticated
        Controller->>ZoneSvc: create_zoning(user, description, municipalities)
        ZoneSvc->>ZoneDao: save(Zoning)
        ZoneDao->>DB: INSERT zoning and links
        DB-->>ZoneDao: zoning id
        ZoneDao-->>ZoneSvc: Zoning
        ZoneSvc-->>Controller: Zoning
        Controller-->>User: created zoning
    end
```
