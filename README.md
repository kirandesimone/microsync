# microsync

Microsync is a RESTful API microservice designed to rapidly synchronize client position data using FastAPI. It uses in-memory read and write caching to combine high-frequency updates before pushing them to a MongoDB database.

## Project Structure

```
microgeo/
├── app/
│   ├── main.py       # app factory, lifespan, exception handlers
│   ├── api/          # endpoints
│   ├── database/     # database connection(s)
│   ├── middleware/   # database middleware
│   ├── schemas/      # database schemas
│   ├── services/     # Ochestration
│   ├── models/       # data models
│   └── core/         # Settings via env / .env file, app logics
├── tests/
├── pyproject.toml
└── .env
```

## Public API

### Location

The Location API provides Create, Read, Delete (CRD) operations for user position data segmented by area. Data is exchanged using JSON payloads. 

| User Story                                                      | Method | Path                        | Purpose                                                   |
|-----------------------------------------------------------------|--------|-----------------------------|-----------------------------------------------------------|
| 1. Publish Client Position Updates                              | POST   | `/positions/<clientId>`     | Publish a client's current position                       |
| 2. Receive Client Position Updates<br>3. Sync User Data on Maps | GET    | `/positions/<areaId>`       | Get all current positions for an area                     |        
| 2. Receive Client Position Updates<br>3. Sync User Data on Maps | GET    | `/positions/<areaId>/posts` | Get user posts for an area with optional timestamp filter |
|                                                                 | DELETE | `/positions/<areaId>/<id>`  | Delete a specific position entry                          |

### Fast Positions

Fast Positions is an API that allows clients to publish position updates in near real-time. This api uses a [write- and read-cache](#write-cache) to coalesce position updates per user and provide a single point of truth for clients. The caches introduce a small latency between client and server.

| User Story                         | Method | Path                      | Purpose                                     |
|------------------------------------|--------|---------------------------|---------------------------------------------|
| 1. Publish Client Position Updates | POST   | `/fast-positions/publish` | Client publishes current batch of positions |
| 2. Receive Client Position Updates | GET    | `/fast-positions`         | Client polls cached positions               |

#### Location API Usage Examples

**Publish a Position (POST `/positions/{clientId}`)**
Publishes an update for a specific client. The schema allows for arbitrary additional [key-value pairs](https://en.wikipedia.org/wiki/Key%E2%80%93value_database) to be passed in the JSON payload.
*Request Body:*
```json
{
  "x": 34.05,
  "y": -118.24,
  "timestamp": "2026-05-31T21:00:00Z",
  "areaId": "portland",
  "public": true
}
```
*Response (201 Created):*
```json
{
  "status": "created",
  "clientId": "user_123",
  "buffered": true,
  "areaId": "portland"
}
```

**Get Area Positions (GET `/positions/{areaId}`)**
Retrieves an array of all currently tracked clients within a specified `areaId`.
*Response (200 OK):*
```json
[
  {
    "user_id": "user_123",
    "x": 34.05,
    "y": -118.24,
    "timestamp": "2026-05-31T21:00:00+00:00",
    "areaId": "portland",
    "public": true
  }
]
```

### Fast Positions

Fast Positions is an API that allows clients to publish position updates in near [real-time](https://en.wikipedia.org/wiki/Real-time_computing). This API uses a [write- and read-cache](#write-cache) to coalesce position updates per user and provide a single point of truth for clients. The caches introduce a small [latency](https://en.wikipedia.org/wiki/Latency_(engineering)) between client and server.

| User Story                         | Method | Path                      | Purpose                                     |
|------------------------------------|--------|---------------------------|---------------------------------------------|
| 1. Publish Client Position Updates | POST   | `/fast-positions/publish` | Client publishes current batch of positions |
| 2. Receive Client Position Updates | GET    | `/fast-positions`         | Client polls cached positions               |

#### Fast Positions Usage Examples

**Publish a Position (POST `/fast-positions/publish`)**
Sends player coordinates directly to the memory cache.
*Request Body:*
```json
{
  "user_id": "player_456",
  "x": 100.5,
  "y": 250.0
}
```
*Response (201 Created):*
```json
{
  "user_id": "player_456",
  "x": 100.5,
  "y": 250.0,
  "timestamp": "2026-05-31T21:00:00.000Z",
  "cached": true
}
```
*(Note: `cached: true` confirms the payload is held in the buffer awaiting background DB insertion).*

**Get All Positions (GET `/fast-positions`)**
Retrieves the most recent coordinate snapshot for all known active players.
*Response (200 OK):*
```json
{
  "positions": [
    {
      "user_id": "player_456",
      "x": 100.5,
      "y": 250.0,
      "timestamp": "2026-05-31T21:00:00.000Z"
    }
  ],
  "count": 1
}
```

## UML Diagram
```mermaid
classDiagram
    class Settings {
        +String app_name
        +String app_version
        +String host
        +Int port
        +String position_collection_name
        +Float position_cache_ttl_seconds
        +Int position_cache_max_pending
        +Float read_cache_refresh_seconds
    }
    class PositionWriteCache {
        -dict[String, _BufferedPosition] _buffer
        -asyncio.Lock _lock
        -asyncio.Task _flush_task
        -AsyncDatabase _db
        +start(db)
        +stop()
        +put(user_id, x, y, timestamp) Bool
        +flush_all()
        -_flush_loop()
        -_flush_all_locked()
    }
    class PositionReadCache {
        -dict[String, PositionRecord] _snapshot
        -asyncio.Task _refresh_task
        -AsyncDatabase _db
        +start(db)
        +stop()
        +get_many() dict[String, PositionRecord]
        -_refresh_loop()
        -_refresh()
    }
    class _BufferedPosition {
        +String user_id
        +Float x
        +Float y
        +DateTime timestamp
        +Int pending_count
    }
    class TimingMiddleware {
        +dispatch(request, call_next) Response
    }
    namespace Api {
        class FastPositions {
            +publish_position(paylod) PositionPublishResponse
            +get_all_positions() AllPositionsResponse
        }
        class Positions {
            +publish_position(clientId, positionData) JSONResponse
            +get_client_positions(areaId) JSONResponse
            +get_user_posts(areaId, since) JSONResponse
            +delete_position(areaId, id) JSONResponse
        }
    }
    namespace Schemas {
        class PositionRecord {
            +String user_id
            +Float x
            +Float y
            +DateTime timestamp
        }
        class PositionPublishRequest {
            +String user_id
            +Float x
            +Float y
        }
        class PositionPublishResponse {
            +String user_id
            +Float x
            +Float y
            +DateTime timestamp
            +Bool cached
        }
        class AllPositionsResponse {
            +list[PositionRecord] positions
            +Int count
        }
    }
    namespace Models {
        class PositionData {
            +Float x
            +Float y
            +String timestamp
            +String areaId
            +Bool public
        }
    }
    
    PositionWriteCache --* _BufferedPosition
    PositionWriteCache --> Settings
    
    PositionReadCache --> PositionRecord
    PositionReadCache --> Settings
    
    FastPositions --> PositionPublishRequest
    FastPositions --> PositionPublishResponse
    FastPositions --> AllPositionsResponse
    
    Positions --> PositionData
    Positions --> PositionWriteCache
    Positions --> PositionReadCache
```

## Sequencing Diagram
```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant MW as TimingMiddleware
    participant API as FastAPI Router<br/>(/fast-positions)
    participant WC as PositionWriteCache<br/>(in-memory buffer)
    participant FT as Flush Task<br/>(background)
    participant RC as PositionReadCache<br/>(in-memory snapshot)
    participant RT as Refresh Task<br/>(background)
    participant DB as MongoDB@{ "type" : "database" }
    
    Note over FT,RT: Started in lifespan on app boot<br/>(main.py create_lifespan)
    
    Note over Client,DB: Write path — POST /fast-positions/publish
    Client->>MW: POST /fast-positions/publish<br/>{user_id, x, y}
    MW->>MW: t0 = perf_counter()
    MW->>API: forward request
    API->>API: now = utcnow()
    API->>WC: put(user_id, x, y, now)
    WC->>WC: acquire lock,<br/>upsert _BufferedPosition,<br/>pending_count++
    alt pending_count >= max_pending
      WC->>WC: _flush_all_locked()
      WC->>DB: bulk_write(InsertOne[...])
      DB-->>WC: ack
      WC-->>API: cached = False (flushed)
    else under threshold
      WC-->>API: cached = True (buffered)
    end
    API-->>MW: 201 PositionPublishResponse
    MW->>MW: set X-Process-Time-Ms
    MW-->>Client: 201 + headers
    
    Note over Client,DB: Read path — GET /fast-positions/
    Client->>MW: GET /fast-positions/
    MW->>API: forward
    API->>RC: get_many()
    RC-->>API: dict copy of snapshot
    API-->>MW: 200 AllPositionsResponse<br/>{positions, count}
    MW-->>Client: 200 + X-Process-Time-Ms
    
    Note over FT,DB: Background flush loop (every position_cache_ttl_seconds)
    loop forever
      FT->>FT: sleep(TTL)
      FT->>WC: flush_all()
      WC->>WC: snapshot entries, clear buffer
      WC->>DB: bulk_write(InsertOne[...], ordered=False)
      alt success
          DB-->>WC: ack
      else failure
          DB-->>WC: error
          WC->>WC: re-buffer entries via setdefault
      end
    end
    
    Note over RT,DB: Background refresh loop (every read_cache_refresh_seconds)
    loop forever
      RT->>RT: sleep(refresh_seconds)
      RT->>DB: aggregate([sort ts desc, group by user_id first])
      DB-->>RT: latest doc per user_id
      RT->>RC: replace _snapshot
      Note right of RC: On error: keep stale snapshot
    end
    
    Note over Client,DB: Shutdown: lifespan awaits write_cache.flush_all(),<br/>then disconnect_db()
```

## MongoDB

### Write Cache

Implements a two-sided position caching layer in front of MongoDB so per-tick position updates from clients don't translate into per-tick DB writes, and so client poll requests resolve from an in-memory snapshot instead of querying Mongo directly.

- PositionWriteCache: coalesces position updates per user into an in-memory buffer, then bulk-flushes to MongoDB on a TTL tick or when any single user accumulates position_cache_max_pending updates.
- PositionReadCache: maintains a user_id -> PositionRecord snapshot rebuilt periodically from MongoDB via a single `$sort + $group` aggregation pipeline. get_many() returns a shallow copy so client reads are a single dict lookup.

The free tier allows up to 100 operations per second. That's shared across all reads and writes hitting the cluster. With 5 clients polling at `20 fps tick rate = 100 writes/sec`, we're sitting right at the ceiling before a single read happens. With the 3-second write cache, that drops to roughly `5 clients ÷ 3 seconds = ~2 writes/sec`, plus poll calls. At 5 clients polling a few times a second, we're looking at maybe 15–20 ops/sec total, well within budget.


### Development Environment
Create and populate `.env.mongodb` environment file in the local project root. The environment file requires the following variables to be defined:


```
MONGODB_URI=<Replace with MongoDB Connection String>
MONGODB_DB_NAME=<Replace with Database Name>
```

> [!CAUTION]
> Do not commit `.env.mongodb` to git

## Git Workflow

#### Sync main before branching
1. `git checkout main`
2. `git pull --rebase origin main`

#### Create branch
1. `git checkout -b feature/task`

#### Write Code/Commit locally
1. `git add .`
2. `git commit -m "message"`

#### To squash a small commit into a bigger one
1. `git rebase -i HEAD~n`

#### Update branch before pushing
1. `git fetch origin` (or git pull)
2. `git rebase origin/main`

#### Push for PR
1. `git push -u origin feature/task`

