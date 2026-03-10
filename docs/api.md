# SilentCircle Backend API (Phase 1)

## Onboarding Policy
- Account onboarding is invite-only.
- Expected path:
  1. staff/admin creates invite via `/api/admin/invites/`
  2. recipient opens `/invite/<token>` in frontend
  3. recipient completes password + public key registration
  4. user then logs in normally from `/login` afterward
- Staff users should use dedicated frontend shell at `/admin`; non-staff should use `/chat`.

## Auth Endpoints

### `GET /api/auth/invite/<token>/validate/`
- Auth: Public
- 200:
```json
{ "valid": true, "username": "alice", "display_name": "Alice" }
```
- 404 when token missing/invalid/expired/used.

### `POST /api/auth/invite/<token>/complete/`
- Auth: Public
- Request:
```json
{
  "password": "...",
  "confirm_password": "...",
  "x25519_public_key": "...",
  "ed25519_public_key": "..."
}
```
- Behavior: validates token, sets password + pubkeys, marks invite as used, returns access token and sets refresh cookie.
- 200:
```json
{ "access": "<jwt>", "user": { "id": "...", "username": "...", "display_name": "...", "is_staff": false } }
```
- 400: used/expired token or payload validation errors.
- 404: invalid token.

### `POST /api/auth/login/`
- Auth: Public
- Request: `{ "username": "...", "password": "..." }`
- 200: same shape as invite complete.
- 401: invalid credentials or inactive user.

### `POST /api/auth/logout/`
- Auth: JWT required
- Behavior: blacklists refresh token if present in cookie, deletes refresh cookie.
- 204 on success.

### `POST /api/auth/token/refresh/`
- Auth: Public (cookie-based)
- Reads refresh token only from cookie.
- 200:
```json
{ "access": "<jwt>" }
```
- Sets rotated refresh cookie.
- 401 when cookie missing/invalid.
- Frontend boot flow should call this endpoint on page load before deciding logged-in state.

### `GET /api/auth/ws-ticket/`
- Auth: JWT required
- Behavior: writes `ws_ticket:<uuid> -> <user_id>` in Redis with 30-second TTL.
- 200:
```json
{ "ticket": "<uuid>" }
```

### `POST /api/auth/change-password/`
- Auth: JWT required
- Request:
```json
{ "old_password": "...", "new_password": "..." }
```
- `new_password` minimum length: 12.
- Behavior: verifies old password, sets new one, blacklists all outstanding refresh tokens.
- 200:
```json
{ "detail": "Password changed." }
```

## User Endpoints

### `GET /api/users/me/`
- Auth: JWT required
- 200:
```json
{ "id": "...", "username": "...", "display_name": "...", "is_staff": false }
```

### `PATCH /api/users/me/`
- Auth: JWT required
- Purpose: update profile/public keys for the authenticated user (used by New Device flow).
- Accepted fields:
```json
{
  "display_name": "...",
  "x25519_public_key": "...",
  "ed25519_public_key": "..."
}
```
- 200: returns current user summary.

### `GET /api/users/search/?q=<query>`
- Auth: JWT required
- Minimum `q` length: 2
- Returns max 10 active users, excludes requester.

## Admin Endpoints (staff only)

### Users
- `GET /api/admin/users/` list users
- `POST /api/admin/users/` create user
- `GET /api/admin/users/<uuid:pk>/` retrieve user
- `PUT/PATCH /api/admin/users/<uuid:pk>/` update user
- `DELETE /api/admin/users/<uuid:pk>/` delete user
- `POST /api/admin/users/<uuid:pk>/deactivate/` body `{ "is_active": true|false }`

### Invites
- `GET /api/admin/invites/` list invites
- `POST /api/admin/invites/` body:
```json
{ "assigned_to": "<user_uuid>", "expires_hours": 24 }
```
- `DELETE /api/admin/invites/<uuid:pk>/` revoke only if unused.

## Cookie Contract
- Name: `AUTH_REFRESH_COOKIE_NAME` (default `refresh_token`)
- `HttpOnly`: true
- `Secure`: env-configurable (dev default false, base/prod default true)
- `SameSite`: env-configurable (default `Lax`)
- Max age: env-configurable (default 7 days)
