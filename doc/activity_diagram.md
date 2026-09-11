# Activity diagrams

## 1. Initialize the databases

```mermaid
flowchart TD
    start([Start initialization]) --> createDb[Create database schema]
    createDb --> weather[Download Météo-France files by department]
    weather --> filterMeteo[Keep useful columns and dates from 1990]
    filterMeteo --> dedup{Duplicates on station and date?}
    dedup -->|Yes| dropDup[Drop duplicate rows]
    dedup -->|No| stations
    dropDup --> stations[Extract distinct weather stations]
    stations --> saveMeteo[Insert stations and daily reports]
    saveMeteo --> geo[Download municipalities from geo.api.gouv.fr]
    geo --> alti[Enrich each commune with altitude]
    alti --> hierarchy[Build department and region hierarchy]
    hierarchy --> saveGeo[Insert municipalities, departments and regions]
    saveGeo --> ready([Databases ready])
```

## 2. Estimate local temperatures

```mermaid
flowchart TD
    start([Start estimation]) --> nearest[Find n nearest stations]
    nearest --> found{At least one station with reports?}
    found -->|No| fail([Cannot estimate temperature])
    found -->|Yes| reports[Load daily Tmin / Tmax / Tmean]
    reports --> loopDay[For each day of the period]
    loopDay --> correct[Apply altitude correction if needed]
    correct --> weights[Compute IDW weights from Haversine distances]
    weights --> interp[Interpolate daily temperature]
    interp --> moreDays{More days?}
    moreDays -->|Yes| loopDay
    moreDays -->|No| done([Daily temperature series])
```

## 3. Compute a punctual DJU

```mermaid
flowchart TD
    start([Client sends POST /dju/point]) --> validate{Parameters valid?}
    validate -->|No| badReq[Return 400 Bad Request]
    badReq --> endBad([End])
    validate -->|Yes| cache{Reusable result in database?}
    cache -->|Yes| formatCached[Format cached DJU]
    formatCached --> respondOk
    cache -->|No| estimate[Estimate daily temperatures]
    estimate --> tempsOk{Temperatures available?}
    tempsOk -->|No| noData[Return 404 / 422]
    noData --> endNoData([End])
    tempsOk -->|Yes| daily[For each day: heating DJU = max threshold - T, 0]
    daily --> cooling{Cooling threshold provided?}
    cooling -->|Yes| dailyCool[Cooling DJU = max T - threshold, 0]
    cooling -->|No| aggregate
    dailyCool --> aggregate[Aggregate by time step: daily, weekly, monthly, yearly]
    aggregate --> save[Save DjuCalculation and DjuResult]
    save --> formatCached2[Format results]
    formatCached2 --> respondOk[Return JSON to client]
    respondOk --> endOk([End])
```

## 4. Compute a zone DJU

```mermaid
flowchart TD
    start([Client sends POST /dju/zone]) --> validate{Parameters valid?}
    validate -->|No| badReq[Return 400 Bad Request]
    badReq --> endBad([End])
    validate -->|Yes| loadZone[Load zone and its municipalities]
    loadZone --> exists{Zone found?}
    exists -->|No| notFound[Return 404 Not Found]
    notFound --> end404([End])
    exists -->|Yes| kind{Public department or region?}
    kind -->|No, personal zoning| auth{User authenticated and owner?}
    auth -->|No| forbidden[Return 401 / 403]
    forbidden --> endAuth([End])
    auth -->|Yes| cache
    kind -->|Yes| cache{Reusable result in database?}
    cache -->|Yes| formatCached[Format cached DJU]
    formatCached --> respondOk
    cache -->|No| loopMuni[For each municipality]
    loopMuni --> pointDju[Compute punctual DJU at commune coordinates]
    pointDju --> moreMuni{More municipalities?}
    moreMuni -->|Yes| loopMuni
    moreMuni -->|No| agg[Aggregate commune DJU, e.g. population-weighted]
    agg --> save[Save DjuCalculation and DjuResult]
    save --> respondOk[Return JSON to client]
    respondOk --> endOk([End])
```

## 5. Consult zonings

```mermaid
flowchart TD
    start([Client requests zonings]) --> type{Filter by type?}
    type -->|Department| depts[Load departments and municipalities]
    type -->|Region| regions[Load regions, departments and municipalities]
    type -->|All| all[Load all official zones]
    depts --> respond
    regions --> respond
    all --> respond[Return JSON list]
    respond --> endOk([End])
```

## 6. Create or import a personalized zoning

An authenticated user defines a custom set of municipalities, either by sending
a list in the request body or by importing a CSV / JSON file.

```mermaid
flowchart TD
    start([User creates or imports a zoning]) --> auth{Authenticated?}
    auth -->|No| unauth[Return 401 Unauthorized]
    unauth --> endUnauth([End])
    auth -->|Yes| source{Import from file?}
    source -->|Yes| parse[Parse CSV or JSON]
    parse --> formatOk{File format valid?}
    formatOk -->|No| badFile[Return 400 Bad Request]
    badFile --> endFile([End])
    formatOk -->|Yes| resolve
    source -->|No| resolve[Resolve municipality identifiers]
    resolve --> known{All communes exist?}
    known -->|No| unknown[Return 400 unknown municipalities]
    unknown --> endUnknown([End])
    known -->|Yes| save[Insert Zoning and commune links]
    save --> created[Return 201 Created]
    created --> endOk([End])
```

## 7. Manage a personalized zoning

```mermaid
flowchart TD
    start([User updates or deletes a zoning]) --> auth{Authenticated?}
    auth -->|No| unauth[Return 401 Unauthorized]
    unauth --> endUnauth([End])
    auth -->|Yes| load[Load zoning by id]
    load --> found{Zoning found?}
    found -->|No| notFound[Return 404 Not Found]
    notFound --> end404([End])
    found -->|Yes| owner{User is the owner?}
    owner -->|No| forbidden[Return 403 Forbidden]
    forbidden --> end403([End])
    owner -->|Yes| action{Requested action?}
    action -->|Update| update[Apply description and commune changes]
    update --> persist[Save changes]
    persist --> ok[Return 200 OK]
    ok --> endOk([End])
    action -->|Delete| deleteZ[Delete zoning and links]
    deleteZ --> gone[Return 204 No Content]
    gone --> endDel([End])
```
