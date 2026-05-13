# microsync

## Project Structure

```
microgeo/
├── app/
│   ├── main.py       # app factory, lifespan, exception handlers
│   ├── api/          # endpoints (area, point, search)
│   ├── services/     # Ochestration, async Overpass, async Nominatim
│   ├── models/       # request/response models
│   └── core/         # Settings via env / .env file, app logics
├── tests/
├── pyproject.toml
└── .env
```

## MongoDB
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

