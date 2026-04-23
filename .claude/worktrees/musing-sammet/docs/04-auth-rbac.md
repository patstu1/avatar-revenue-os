# Authentication & RBAC — AI Avatar Revenue OS

## Authentication Flow

1. **Registration** — `POST /api/v1/auth/register`
   - Creates organization + admin user in a single transaction
   - Password hashed with bcrypt
   - Returns user object

2. **Login** — `POST /api/v1/auth/login`
   - Validates email + password
   - Returns JWT access token (HS256, 24h expiry)
   - Creates audit log entry

3. **Token Usage** — `Authorization: Bearer <token>`
   - All protected endpoints require valid JWT
   - Token contains user UUID in `sub` claim
   - Token decoded and user fetched from DB on every request

4. **Current User** — `GET /api/v1/auth/me`
   - Returns authenticated user profile

## RBAC Enforcement

### Role Hierarchy

```
ADMIN (level 3) — Full access to everything
  └── OPERATOR (level 2) — Can read and write resources
        └── VIEWER (level 1) — Read-only access
```

### Implementation

The `RequireRole` dependency class enforces minimum role levels:

```python
class RequireRole:
    HIERARCHY = {UserRole.ADMIN: 3, UserRole.OPERATOR: 2, UserRole.VIEWER: 1}

    def __init__(self, minimum_role: UserRole):
        self.minimum_role = minimum_role

    async def __call__(self, current_user: CurrentUser) -> User:
        # Compares user's role level against required level
        # Returns 403 if insufficient
```

### Dependency Shortcuts

| Dependency | Minimum Role | Used For |
|-----------|-------------|----------|
| `CurrentUser` | Any authenticated | Read endpoints |
| `ViewerUser` | Viewer+ | Explicit read gates |
| `OperatorUser` | Operator+ | Create, update, delete |
| `AdminUser` | Admin only | Settings, org config |

### Endpoint Protection Map

| Endpoint | Method | Required Role |
|----------|--------|--------------|
| `/api/v1/brands/` | GET | CurrentUser |
| `/api/v1/brands/` | POST | CurrentUser* |
| `/api/v1/avatars/` | GET | CurrentUser |
| `/api/v1/avatars/` | POST/PATCH/DELETE | OperatorUser |
| `/api/v1/offers/` | POST/DELETE | CurrentUser* |
| `/api/v1/accounts/` | POST/PATCH/DELETE | OperatorUser |
| `/api/v1/providers/*` | POST/PATCH/DELETE | OperatorUser |
| `/api/v1/settings/*` | GET/PATCH | AdminUser |
| `/api/v1/dashboard/*` | GET | CurrentUser |

*Brands and offers currently use CurrentUser for creation. Will tighten to OperatorUser in Phase 2.

## Organization Scoping

All data access is scoped to the user's organization:
- Brands are filtered by `organization_id`
- All child resources (avatars, offers, accounts) are accessed through brand ownership
- Cross-organization access is blocked at the router level
