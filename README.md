# OISSU CONNECT — API

Backend of **OISSU CONNECT**: suivi et traçabilité des performances des athlètes
du sport scolaire et universitaire. Implements the V1 described in
`OISSU_CONNECT_Conception_Technique_V1_Seed.docx`.

Built on a lean, batteries-included **FastAPI** scaffold generated with
[shaapi](https://github.com/Shalom-302/shaapi): async SQLAlchemy + Alembic,
Postgres, Redis, JWT auth, file storage, i18n and a one-command Docker workflow.

> **Les données de démonstration sont fictives.** Le seed (`seed-demo`) génère
> des athlètes, établissements, compétitions et performances inventés, destinés
> uniquement à rendre le pitch crédible. Ils ne représentent pas des données
> réelles de l'OISSU et doivent être supprimés avant toute mise en production
> (doc §12, §18).

## Domain in one screen

```
PUBLIC
 └── Accueil ── Login  ─┬─ role=USER  ──> /dashboard        (espace athlète)
                        └─ role=ADMIN ──> /admin/dashboard  (pilotage)

User 1 ─── 1 Athlete        Athlete 1 ─── N Performance
```

Two roles only in V1: `USER` (an athlete) and `ADMIN`. There is **no public
sign-up**: an administrator creates the account and the athlete profile together,
in one transaction, from `POST /api/v1/admin/athletes`.

## API surface

The API is mounted at the root, so the URLs match the design document exactly.

| Space | Endpoints |
| --- | --- |
| Auth | `POST /api/v1/auth/login` · `GET /api/v1/auth/me` · `POST /api/v1/auth/logout` · `POST /api/v1/auth/token/new` |
| USER | `GET|PATCH /api/v1/users/me` · `GET|PATCH /api/v1/athletes/me` · `GET /api/v1/athletes/me/performances` · `GET /api/v1/dashboard` |
| ADMIN | `GET /api/v1/admin/dashboard` · `GET|POST /api/v1/admin/athletes` · `GET /api/v1/admin/athletes/filters` · `GET|PATCH|DELETE /api/v1/admin/athletes/{id}` · `PATCH /api/v1/admin/athletes/{id}/status` · `GET /api/v1/admin/athletes/{id}/performances` · `GET|POST /api/v1/admin/performances` · `GET|PATCH|DELETE /api/v1/admin/performances/{id}` |

Every `/admin/*` route is guarded server-side by `DependsAdmin`
(`backend/common/security/permission.py`), never by frontend routing alone.

- **Swagger**: http://localhost:8000/api/v1/docs
- **Health**: http://localhost:8000/health

## Demonstration dataset

```bash
shaapi shell
python -m backend.cli seed-demo            # 1 admin + 60 athletes + ~360 performances
python -m backend.cli seed-demo --purge    # remove every demo record
```

The seed refuses to run unless `ENVIRONMENT=dev` (override with
`OISSU_SEED_FORCE=1` on a throwaway database). Demo records are recognisable by
their `@oissu-demo.ci` email domain and `OISSU-DEMO-` licence prefix, which is
what `--purge` keys on when the real data arrives.

> The design document writes these addresses as `@oissu.local`. `.local` is a
> reserved special-use name that `EmailStr` refuses, so accounts created with it
> could never log in; `.ci` keeps them just as obviously Ivorian and fictional
> while staying valid. `--purge` still removes `.local` rows from any database
> seeded before the change.

Default credentials (configurable with `ADMIN_EMAIL` / `ADMIN_PASSWORD`):

| Role | Login | Password |
| --- | --- | --- |
| ADMIN | `admin.demo@oissu-demo.ci` | `OissuDemo2026!` |
| USER | `athlete001@oissu-demo.ci` | `AthleteDemo2026!` |

## Frontend

The Next.js client lives in its own repository with its own Docker
configuration per branch (`dev`, `staging`, `main`). Point the API at it with
`CORS_ALLOWED_ORIGINS` in `.env`.

## Branches and Docker configuration

Three branches, **the same source code**, one complete `docker-compose.yml` per
branch. What you read in that file on a given branch is exactly what runs there.

| Branch | `docker-compose.yml` describes |
| --- | --- |
| `dev` | Builds the image from the checkout, bind-mounts the source for hot reload, publishes Postgres and MinIO for local tooling |
| `staging` | Pulls `:staging` from GHCR, joins the external `dokploy-network`, `ENVIRONMENT=preprod`, memory cap and log rotation |
| `main` | Pulls `:main`, joins `dokploy-network`, `ENVIRONMENT=prod`, `DB_AUTO_CREATE=false`, `no-new-privileges`, bounded restart policy |

> **There is deliberately no `docker-compose.override.yml`.** Docker Compose only
> auto-loads an override when it discovers the files itself; deploy tools pass an
> explicit `-f <path>`, and an overlay is then **silently ignored**. Verified:
> `docker compose config` on `staging` resolved to `:staging` on
> `dokploy-network`, while `docker compose -f docker-compose.yml config` in the
> same checkout resolved to `:main` on a private bridge — a stack that starts,
> looks healthy and is wrong. One self-contained file per branch removes the trap.

The cost is that shared changes (a Postgres version bump, say) conflict when
merging `dev` → `staging` → `main`. That is the intended trade: a conflict you
resolve beats a deployment that silently ignores half its configuration.

## Container image (GHCR)

`.github/workflows/docker-publish.yml` builds and pushes on every push to a
deployment branch:

| Branch or tag | Image |
| --- | --- |
| `dev` | `ghcr.io/shalom-302/backendoissu:dev` |
| `staging` | `ghcr.io/shalom-302/backendoissu:staging` |
| `main` | `ghcr.io/shalom-302/backendoissu:main` and `:latest` |
| `v1.2.3` | `ghcr.io/shalom-302/backendoissu:1.2.3`, `:1.2`, `:1` |

Every build is also tagged with the short commit SHA, so a deployment can be
pinned to an exact commit with `API_IMAGE`.

The workflow authenticates with the repository's own `GITHUB_TOKEN` — no secret
to create. **The package is private by default.** Either make it public
(GitHub → Packages → the package → Package settings → Change visibility), or add
a registry to Dokploy with a personal access token holding `read:packages`.

## Deploying on Dokploy

Create a **Compose** application:

| Field | Value |
| --- | --- |
| Repository | `Shalom-302/backendoissu` |
| Branch | `staging` or `main` |
| Compose path | `docker-compose.yml` |

The same path on every branch — the branch alone decides the environment,
because the file itself differs.

The API joins `dokploy-network` **in addition to** the project's own `oissu`
network: `oissu` is how it reaches Postgres, Redis and MinIO, and
`dokploy-network` is how the frontend reaches it by container name —

```
API_INTERNAL_URL=http://oissu_api:8000
```

The datastores stay on `oissu` only, so nothing but the API is visible to the
other stacks sharing the Dokploy network.

> **The server will refuse to start on staging and production until the secrets
> are real.** Those branches force `ENVIRONMENT=preprod` / `prod`, and the
> settings validator rejects the development defaults for `TOKEN_SECRET_KEY`,
> `OPERA_LOG_ENCRYPT_SECRET_KEY`, `POSTGRES_PASSWORD` and `MINIO_SECRET_KEY`.
> Set them in the environment Dokploy injects. That check is the point: it fails
> loudly instead of running a deployment with forgeable tokens.

## Quick start

```bash
shaapi up              # build + start the whole stack (dev: hot-reload)
shaapi db apply        # apply database migrations
shaapi auth init       # create an admin user to log into Swagger
shaapi storage init    # create the object-storage bucket
```

Then open:

- **API**: http://localhost:8000
- **Swagger**: http://localhost:8000/api/v1/docs

> On Linux/macOS you can use the bundled `./docker-run.sh` instead of `shaapi`
> if you prefer a plain shell script — both drive the same Docker stack.

## Commands

Everything runs through `shaapi` (cross-platform) — no need to memorize raw
`docker compose` incantations. Commands are grouped by domain:

**Lifecycle**

```bash
shaapi up [--monitoring] [--prod]   # build + start (monitoring/prod optional)
shaapi down                         # stop and remove containers
shaapi logs [service]               # tail logs (e.g. shaapi logs api)
shaapi restart [service]            # restart all, or one service
shaapi ps                           # container status
shaapi shell                        # bash inside the api container
shaapi redis                        # redis-cli inside Redis
```

**Database (`db`)**

```bash
shaapi db generate --message "add posts table"   # autogenerate a migration
shaapi db apply                                   # alembic upgrade head
shaapi db preview                                 # SQL that apply would run
shaapi db pending                                 # current revision vs. head
shaapi db shell                                   # psql inside Postgres
```

**Auth (`auth`) & Storage (`storage`)**

```bash
shaapi auth init      # create an admin user (email + password)
shaapi storage init   # ensure the MinIO/S3 bucket exists
```

The equivalent `./docker-run.sh` subcommands exist for shell users on Unix
(`up`, `down`, `logs`, `migrate`, `makemigrations`, `shell`, …).

## What's inside

- **FastAPI** (async) with a layered architecture (`app/`, `common/`, `core/`,
  `crud/`, `models/`, `database/`, `middleware/`, `utils/`).
- **SQLAlchemy 2 + Alembic** migrations on **Postgres** (auto-create tables in
  dev, migrations in prod).
- **Redis** cache + rate limiting.
- **JWT auth** (sign in / sign up) + **Casbin RBAC** (users, roles, permissions).
- **File storage** (MinIO / S3 / GCS).
- **i18n** (English + French) and request-scoped translation middleware.
- **Login & operation logs**, request tracing (correlation id).
- **Realtime** via python-socketio.
- **Opt-in observability** (`shaapi up --monitoring`): Prometheus, Grafana,
  Tempo, Loki.
- **Docker**: multi-stage slim image built with [uv], hot-reload in dev.

## Project structure

```
backend/
├── app/            # Feature sub-apps (admin: auth, users, roles, RBAC, logs)
│   └── admin/
│       ├── api/        # API route handlers
│       ├── schema/     # Pydantic request/response models
│       └── service/    # Business logic
├── common/         # Cross-cutting: security, exceptions, responses, socketio…
├── core/           # Settings (conf.py), app registrar, paths
├── crud/           # Reusable async CRUD over the models
├── database/       # Postgres + Redis connections
├── middleware/     # Access log, i18n, operation log, state
├── models/         # SQLAlchemy models
├── lang/           # i18n message catalogs (en, fr)
├── seeder/         # Database seeds (incl. an example admin)
├── utils/          # Helpers (timezone, encrypt, serializers, health…)
├── cli.py          # In-container commands (used by `shaapi auth init`)
└── main.py         # Application entry point
devops/             # Compose helpers / infra
etc/                # Monitoring configs (only when generated with monitoring)
Dockerfile
docker-compose.yml               # the complete stack for THIS branch
docker-compose.monitoring.yml    # opt-in observability stack
.github/workflows/               # builds and publishes the image to GHCR
docker-run.sh                    # shell runner (Unix); `shaapi` is the cross-platform equivalent
.env.template                    # copied to .env on first run
pyproject.toml / uv.lock         # dependencies, managed with uv
```

## Configuration

On first `shaapi up`, a `.env` is created from `.env.template`. Every value has
a sane default in `backend/core/conf.py`, so you only override what differs.
When running under Docker Compose, the database/Redis/MinIO hosts are pointed
at the container service names automatically.

Common variables:

| Variable | Purpose |
| --- | --- |
| `ENVIRONMENT` | `dev`, `preprod` or `prod`. |
| `POSTGRES_*` | Postgres host, port, user, password, database. |
| `REDIS_*` | Redis host, port, password, database index. |
| `MINIO_*` | Object storage endpoint, keys, bucket. |
| `TOKEN_SECRET_KEY` | Secret used to sign JWT access tokens. |
| `SMTP_*` / `EMAILS_FROM_*` | Outgoing mail. |
| `OBSERVABILITY_ENABLED` / `OTLP_GRPC_ENDPOINT` | Opt-in tracing/metrics export. |

## Database migrations

```bash
shaapi db generate --message "add posts table"   # autogenerate from model changes
shaapi db preview                                 # inspect the SQL first
shaapi db apply                                   # apply (alembic upgrade head)
shaapi db pending                                 # current revision vs. head
```

## Authentication

`shaapi auth init` creates the first admin user (with the `admin` role) inside
the running API container; you then log in from Swagger at `/api/v1/docs`. No
admin is seeded by default — create yours with `shaapi auth init`.

> The bundled `shaapi` runner still prints `/admin/api/v1/docs` in its success
> banner. That was the scaffold's mount point; OISSU CONNECT serves the API at
> the root so the URLs match the design document, so the real address is
> **`/api/v1/docs`**.

## License

MIT
