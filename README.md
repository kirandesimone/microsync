# microsync

## Project Structure

```
microgeo/
├── app/
│   ├── main.py       # app factory, lifespan, exception handlers
│   ├── api/          # endpoints
│   ├── services/     # Ochestration
│   ├── models/       # request/response models
│   └── core/         # Settings via env / .env file, app logics
├── tests/
├── pyproject.toml
└── .env
```

## Public API


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
    class PositionRecord {
        +String user_id
        +Float x
        +Float y
        +DateTime timestamp
    }
    
    PositionWriteCache --> _BufferedPosition
    PositionWriteCache --> Settings
    
    PositionReadCache --> PositionRecord
    PositionReadCache --> Settings

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

