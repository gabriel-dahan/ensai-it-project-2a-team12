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
%%{
  init: {
    "theme": "base",
    "themeVariables": {
      "background": "#ffffff",
      "mainBkg": "#ffffff",
      "textColor": "#111111",
      "primaryColor": "#ffffff",
      "primaryTextColor": "#111111",
      "primaryBorderColor": "#222222",
      "secondaryColor": "#f3f4f6",
      "tertiaryColor": "#ffffff",
      "lineColor": "#222222",
      "actorBkg": "#ffffff",
      "actorBorder": "#222222",
      "actorTextColor": "#111111",
      "actorLineColor": "#222222",
      "signalColor": "#111111",
      "signalTextColor": "#111111",
      "labelBoxBkgColor": "#ffffff",
      "labelBoxBorderColor": "#222222",
      "labelTextColor": "#111111",
      "loopTextColor": "#111111",
      "noteBkgColor": "#fff3cd",
      "noteTextColor": "#111111",
      "noteBorderColor": "#222222",
      "activationBkgColor": "#e5e7eb",
      "activationBorderColor": "#222222",
      "sequenceNumberColor": "#ffffff",
      "fontFamily": "arial",
      "fontSize": "16px"
    }
  }
}%%
sequenceDiagram
    actor Admin
    participant Init as Init scripts
    participant Ext as External sources
    participant DAO as DAO layer
    participant DB as Database

    Admin->>Init: Start database initialization

    Init->>Ext: Download Météo-France temperature files
    Ext-->>Init: SYNOP records
    Init->>Init: Filter, deduplicate from 1990
    Init->>DAO: save_stations_and_reports(data)
    DAO->>DB: INSERT stations and reports
    DB-->>DAO: ok

    Init->>Ext: Fetch communes, departments, regions + altitudes
    Ext-->>Init: Geographic referential
    Init->>DAO: save_zones(...)
    DAO->>DB: INSERT official zonings
    DB-->>DAO: ok

    Init-->>Admin: Databases ready
```

## 2. Compute a punctual DJU (F1)

An anonymous or authenticated client requests heating / cooling DJU for GPS
coordinates, over a period and a time step (daily, weekly, monthly, yearly).
Cached results are reused when available (FO1). Otherwise temperatures are
estimated from nearby stations (inverse distance weighting, optional altitude
correction).

```mermaid
%%{
  init: {
    "theme": "base",
    "themeVariables": {
      "background": "#ffffff",
      "mainBkg": "#ffffff",
      "textColor": "#111111",
      "primaryColor": "#ffffff",
      "primaryTextColor": "#111111",
      "primaryBorderColor": "#222222",
      "secondaryColor": "#f3f4f6",
      "tertiaryColor": "#ffffff",
      "lineColor": "#222222",
      "actorBkg": "#ffffff",
      "actorBorder": "#222222",
      "actorTextColor": "#111111",
      "actorLineColor": "#222222",
      "signalColor": "#111111",
      "signalTextColor": "#111111",
      "labelBoxBkgColor": "#ffffff",
      "labelBoxBorderColor": "#222222",
      "labelTextColor": "#111111",
      "loopTextColor": "#111111",
      "noteBkgColor": "#fff3cd",
      "noteTextColor": "#111111",
      "noteBorderColor": "#222222",
      "activationBkgColor": "#e5e7eb",
      "activationBorderColor": "#222222",
      "sequenceNumberColor": "#ffffff",
      "fontFamily": "arial",
      "fontSize": "16px"
    }
  }
}%%
sequenceDiagram
    actor Client
    participant Controller as DjuController
    participant Service as DjuService
    participant DAO as DAO layer
    participant DB as Database

    Client->>Controller: POST /dju/point
    Controller->>Service: calculate_point_dju(params)

    Service->>DAO: find_reusable_result(params)
    DAO->>DB: SELECT cached DJU
    DB-->>DAO: result or none
    DAO-->>Service: cached?

    alt Cached result available
        Service-->>Controller: list[DjuResult]
    else Compute
        Service->>DAO: get nearby stations and reports
        DAO->>DB: SELECT stations / temperatures
        DB-->>Service: meteorological data
        Service->>Service: IDW + altitude, compute and aggregate DJU
        Service->>DAO: save(DjuCalculation)
        DAO->>DB: INSERT results
        Service-->>Controller: list[DjuResult]
    end

    Controller-->>Client: JSON response
```

## 3. Consult public zonings (F2)

Any client can list official geographic zones (departments and regions) and
their municipalities. These zonings are available to every user.

```mermaid
%%{
  init: {
    "theme": "base",
    "themeVariables": {
      "background": "#ffffff",
      "mainBkg": "#ffffff",
      "textColor": "#111111",
      "primaryColor": "#ffffff",
      "primaryTextColor": "#111111",
      "primaryBorderColor": "#222222",
      "secondaryColor": "#f3f4f6",
      "tertiaryColor": "#ffffff",
      "lineColor": "#222222",
      "actorBkg": "#ffffff",
      "actorBorder": "#222222",
      "actorTextColor": "#111111",
      "actorLineColor": "#222222",
      "signalColor": "#111111",
      "signalTextColor": "#111111",
      "labelBoxBkgColor": "#ffffff",
      "labelBoxBorderColor": "#222222",
      "labelTextColor": "#111111",
      "loopTextColor": "#111111",
      "noteBkgColor": "#fff3cd",
      "noteTextColor": "#111111",
      "noteBorderColor": "#222222",
      "activationBkgColor": "#e5e7eb",
      "activationBorderColor": "#222222",
      "sequenceNumberColor": "#ffffff",
      "fontFamily": "arial",
      "fontSize": "16px"
    }
  }
}%%
sequenceDiagram
    actor Client
    participant Controller as ZoneController
    participant Service as ZoneService
    participant DAO as DAO layer
    participant DB as Database

    Client->>Controller: GET /zones?type=department|region
    Controller->>Service: list_public_zones(type)
    Service->>DAO: find_by_type(type)
    DAO->>DB: SELECT zones and municipalities
    DB-->>DAO: zone rows
    DAO-->>Service: list[GeographicZone]
    Service-->>Controller: departments or regions
    Controller-->>Client: JSON list of public zonings
```

## 4. Compute a zone DJU (F3)

DJU are computed on a territory (department, region, or custom zoning) with a
given period, time step and granularity. For official zonings the client does
not need to be authenticated. For a personal zoning, authentication is
required. Municipality-level DJU are then aggregated (for example
population-weighted).

```mermaid
%%{
  init: {
    "theme": "base",
    "themeVariables": {
      "background": "#ffffff",
      "mainBkg": "#ffffff",
      "textColor": "#111111",
      "primaryColor": "#ffffff",
      "primaryTextColor": "#111111",
      "primaryBorderColor": "#222222",
      "secondaryColor": "#f3f4f6",
      "tertiaryColor": "#ffffff",
      "lineColor": "#222222",
      "actorBkg": "#ffffff",
      "actorBorder": "#222222",
      "actorTextColor": "#111111",
      "actorLineColor": "#222222",
      "signalColor": "#111111",
      "signalTextColor": "#111111",
      "labelBoxBkgColor": "#ffffff",
      "labelBoxBorderColor": "#222222",
      "labelTextColor": "#111111",
      "loopTextColor": "#111111",
      "noteBkgColor": "#fff3cd",
      "noteTextColor": "#111111",
      "noteBorderColor": "#222222",
      "activationBkgColor": "#e5e7eb",
      "activationBorderColor": "#222222",
      "sequenceNumberColor": "#ffffff",
      "fontFamily": "arial",
      "fontSize": "16px"
    }
  }
}%%
sequenceDiagram
    actor Client
    participant Controller as DjuController
    participant Service as DjuService
    participant DAO as DAO layer
    participant DB as Database

    Client->>Controller: POST /dju/zone
    Note over Controller: Auth required for personal zonings
    Controller->>Service: calculate_zone_dju(zone, params)

    Service->>DAO: find_reusable_result(zone, params)
    DAO->>DB: SELECT cached DJU
    DB-->>DAO: result or none
    DAO-->>Service: cached?

    alt Cached result available
        Service-->>Controller: list[DjuResult]
    else Compute
        Service->>DAO: get municipalities of the zone
        DAO->>DB: SELECT municipalities
        DB-->>Service: list[Municipality]
        Service->>Service: Point DJU per municipality, then aggregate
        Service->>DAO: save(DjuCalculation)
        DAO->>DB: INSERT results
        Service-->>Controller: list[DjuResult]
    end

    Controller-->>Client: JSON response
```

## 5. Authenticate a user

Authentication is required before creating, importing or managing personal
zonings (F4).

```mermaid
%%{
  init: {
    "theme": "base",
    "themeVariables": {
      "background": "#ffffff",
      "mainBkg": "#ffffff",
      "textColor": "#111111",
      "primaryColor": "#ffffff",
      "primaryTextColor": "#111111",
      "primaryBorderColor": "#222222",
      "secondaryColor": "#f3f4f6",
      "tertiaryColor": "#ffffff",
      "lineColor": "#222222",
      "actorBkg": "#ffffff",
      "actorBorder": "#222222",
      "actorTextColor": "#111111",
      "actorLineColor": "#222222",
      "signalColor": "#111111",
      "signalTextColor": "#111111",
      "labelBoxBkgColor": "#ffffff",
      "labelBoxBorderColor": "#222222",
      "labelTextColor": "#111111",
      "loopTextColor": "#111111",
      "noteBkgColor": "#fff3cd",
      "noteTextColor": "#111111",
      "noteBorderColor": "#222222",
      "activationBkgColor": "#e5e7eb",
      "activationBorderColor": "#222222",
      "sequenceNumberColor": "#ffffff",
      "fontFamily": "arial",
      "fontSize": "16px"
    }
  }
}%%
sequenceDiagram
    actor User
    participant Controller as UserController
    participant Service as AuthService
    participant DAO as DAO layer
    participant DB as Database

    User->>Controller: POST /user/login
    Controller->>Service: authenticate(credentials)
    Service->>DAO: find_by_username(username)
    DAO->>DB: SELECT user
    DB-->>DAO: user row
    DAO-->>Service: User
    Service->>Service: Issue session / token
    Service-->>Controller: authenticated User
    Controller-->>User: 200 OK (session)
```

## 6. Create a personalized zoning (F4)

An authenticated user builds a custom territory as a set of municipalities and
stores it for later DJU calculations.

```mermaid
%%{
  init: {
    "theme": "base",
    "themeVariables": {
      "background": "#ffffff",
      "mainBkg": "#ffffff",
      "textColor": "#111111",
      "primaryColor": "#ffffff",
      "primaryTextColor": "#111111",
      "primaryBorderColor": "#222222",
      "secondaryColor": "#f3f4f6",
      "tertiaryColor": "#ffffff",
      "lineColor": "#222222",
      "actorBkg": "#ffffff",
      "actorBorder": "#222222",
      "actorTextColor": "#111111",
      "actorLineColor": "#222222",
      "signalColor": "#111111",
      "signalTextColor": "#111111",
      "labelBoxBkgColor": "#ffffff",
      "labelBoxBorderColor": "#222222",
      "labelTextColor": "#111111",
      "loopTextColor": "#111111",
      "noteBkgColor": "#fff3cd",
      "noteTextColor": "#111111",
      "noteBorderColor": "#222222",
      "activationBkgColor": "#e5e7eb",
      "activationBorderColor": "#222222",
      "sequenceNumberColor": "#ffffff",
      "fontFamily": "arial",
      "fontSize": "16px"
    }
  }
}%%
sequenceDiagram
    actor User
    participant Controller as ZoneController
    participant Service as ZoneService
    participant DAO as DAO layer
    participant DB as Database

    User->>Controller: POST /user/zones
    Controller->>Service: create_zoning(user, description, municipalities)
    Service->>Service: Validate municipalities
    Service->>DAO: save(Zoning)
    DAO->>DB: INSERT zoning and links
    DB-->>DAO: zoning id
    DAO-->>Service: Zoning
    Service-->>Controller: Zoning
    Controller-->>User: 201 Created
```

## 7. Manage a personalized zoning (F4)

The owner can update the description, add or remove municipalities, or delete
a personal zoning.

```mermaid
%%{
  init: {
    "theme": "base",
    "themeVariables": {
      "background": "#ffffff",
      "mainBkg": "#ffffff",
      "textColor": "#111111",
      "primaryColor": "#ffffff",
      "primaryTextColor": "#111111",
      "primaryBorderColor": "#222222",
      "secondaryColor": "#f3f4f6",
      "tertiaryColor": "#ffffff",
      "lineColor": "#222222",
      "actorBkg": "#ffffff",
      "actorBorder": "#222222",
      "actorTextColor": "#111111",
      "actorLineColor": "#222222",
      "signalColor": "#111111",
      "signalTextColor": "#111111",
      "labelBoxBkgColor": "#ffffff",
      "labelBoxBorderColor": "#222222",
      "labelTextColor": "#111111",
      "loopTextColor": "#111111",
      "noteBkgColor": "#fff3cd",
      "noteTextColor": "#111111",
      "noteBorderColor": "#222222",
      "activationBkgColor": "#e5e7eb",
      "activationBorderColor": "#222222",
      "sequenceNumberColor": "#ffffff",
      "fontFamily": "arial",
      "fontSize": "16px"
    }
  }
}%%
sequenceDiagram
    actor User
    participant Controller as ZoneController
    participant Service as ZoneService
    participant DAO as DAO layer
    participant DB as Database

    User->>Controller: PATCH / DELETE /user/zones/{id}
    Controller->>Service: get_zoning(id) for owner
    Service->>DAO: find_zone(id)
    DAO->>DB: SELECT zoning
    DB-->>Service: Zoning

    alt Update
        Service->>DAO: update(Zoning)
        DAO->>DB: UPDATE zoning / links
        Controller-->>User: 200 OK
    else Delete
        Service->>DAO: delete(id)
        DAO->>DB: DELETE zoning
        Controller-->>User: 204 No Content
    end
```

## 8. Import a zoning from a file (FO3)

An authenticated user uploads a CSV or JSON file listing municipalities. The
API parses the file, maps rows to known communes, then stores a personal
zoning (same persistence path as F4).

```mermaid
%%{
  init: {
    "theme": "base",
    "themeVariables": {
      "background": "#ffffff",
      "mainBkg": "#ffffff",
      "textColor": "#111111",
      "primaryColor": "#ffffff",
      "primaryTextColor": "#111111",
      "primaryBorderColor": "#222222",
      "secondaryColor": "#f3f4f6",
      "tertiaryColor": "#ffffff",
      "lineColor": "#222222",
      "actorBkg": "#ffffff",
      "actorBorder": "#222222",
      "actorTextColor": "#111111",
      "actorLineColor": "#222222",
      "signalColor": "#111111",
      "signalTextColor": "#111111",
      "labelBoxBkgColor": "#ffffff",
      "labelBoxBorderColor": "#222222",
      "labelTextColor": "#111111",
      "loopTextColor": "#111111",
      "noteBkgColor": "#fff3cd",
      "noteTextColor": "#111111",
      "noteBorderColor": "#222222",
      "activationBkgColor": "#e5e7eb",
      "activationBorderColor": "#222222",
      "sequenceNumberColor": "#ffffff",
      "fontFamily": "arial",
      "fontSize": "16px"
    }
  }
}%%
sequenceDiagram
    actor User
    participant Controller as ZoneController
    participant Service as ZoneService
    participant DAO as DAO layer
    participant DB as Database

    User->>Controller: POST /user/zones/import (CSV or JSON)
    Controller->>Service: import_zoning(user, file)
    Service->>Service: Parse file and resolve municipalities
    Service->>DAO: save(Zoning)
    DAO->>DB: INSERT zoning and links
    DB-->>DAO: zoning id
    DAO-->>Service: Zoning
    Service-->>Controller: Zoning
    Controller-->>User: 201 Created
```
