# Architecture Foundation — AI Avatar Revenue OS

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Next.js Frontend                   │
│              (TypeScript + Tailwind + RQ)            │
│                   localhost:3001                     │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP / REST
┌──────────────────────▼──────────────────────────────┐
│                   FastAPI Backend                     │
│            (Python 3.11 + Pydantic + SA)             │
│                   localhost:8001                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ Routers  │→ │ Services │→ │ SQLAlchemy Models │   │
│  └──────────┘  └──────────┘  └──────────────────┘   │
└──────┬─────────────────┬────────────────────────────┘
       │                 │
┌──────▼──────┐   ┌──────▼──────┐
│ PostgreSQL  │   │    Redis    │
│  (port 5433)│   │ (port 6380) │
└─────────────┘   └──────┬──────┘
                         │
                  ┌──────▼──────┐
                  │   Celery    │
                  │   Workers   │
                  │  6 queues   │
                  └─────────────┘
```

## Monorepo Structure

```
/apps
  /web          — Next.js frontend (TypeScript, Tailwind, React Query, Zustand)
  /api          — FastAPI backend (Pydantic, service-layer architecture)
/workers        — Celery task workers (6 domain queues)
/packages
  /db           — SQLAlchemy models, Alembic migrations, enums
  /shared-types — Shared type definitions
/infrastructure
  /docker       — Dockerfiles for api and web
/scripts        — Seed data and utilities
/tests          — pytest integration tests
/docs           — This documentation
```

## Service-Layer Architecture

All business logic lives in the service layer, not in routers or UI:

```
Router (thin) → Service (logic) → Model (persistence)
     ↓              ↓                    ↓
  Validation    Business rules      SQLAlchemy ORM
  Auth/RBAC     Audit logging       PostgreSQL
  HTTP codes    Error handling
```

## RBAC Model

Three roles with hierarchical permissions:

| Role     | Level | Can Read | Can Write | Can Admin |
|----------|-------|----------|-----------|-----------|
| ADMIN    | 3     | ✓        | ✓         | ✓         |
| OPERATOR | 2     | ✓        | ✓         | ✗         |
| VIEWER   | 1     | ✓        | ✗         | ✗         |

Enforced via `RequireRole` dependency:
- `CurrentUser` — Any authenticated user
- `ViewerUser` — Viewer+
- `OperatorUser` — Operator+ (required for create/update/delete on resources)
- `AdminUser` — Admin only (required for settings, org config)

## Database Conventions

- **UUID primary keys** on all tables
- **created_at / updated_at** timestamps (timezone-aware) on all tables
- **JSONB** for flexible structured data
- **Enum types** for all categorical fields
- **Indexes** on all foreign keys and frequently queried columns
- **Alembic** for all schema migrations (auto-generated from models)

## Docker Isolation

Project name: `avatar-revenue-os`
Network: `aro-network` (bridge, isolated)
Volumes: `aro_pgdata`, `aro_redisdata`, `aro_web_node_modules`
Container prefix: `aro-*`

Zero port conflicts with other Docker projects.
