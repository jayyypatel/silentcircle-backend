# SilentCircle Backend Architecture

## Purpose
This document is the canonical high-level context for AI-assisted backend work.
If code generation conflicts with this doc, update this doc first or fix the generation.

## Tech Stack
- Framework: Django + Django REST Framework
- Auth: `djangorestframework-simplejwt` with blacklist enabled
- Realtime foundation: Channels + Redis (WS ticket flow only in Phase 1)
- Database: PostgreSQL (Supabase)

## Project Structure
- `silentcircle/settings/`: split settings (`base`, `development`, `production`)
- `apps/users/`: custom user model, auth API, admin API, search API
- `apps/auth_tokens/`: invite token model and admin
- `apps/conversations/`, `apps/messages/`, `apps/realtime/`: placeholders for next phases

## Runtime Flow (Phase 1)
1. Admin creates an invite for a pre-created user.
2. User completes invite or logs in.
3. Backend issues access token in response body.
4. Backend issues refresh token in `HttpOnly` cookie.
5. Client sends `Authorization: Bearer <access>` for protected endpoints.
6. Client refreshes access token via `/api/auth/token/refresh/` using cookie.
7. Client bootstraps session on app load by attempting refresh first, then `/api/users/me/`.
8. For websocket bootstrap, client requests `/api/auth/ws-ticket/`; server stores one-time ticket in Redis (`ws_ticket:<uuid>`, 30s TTL).

## Frontend Conventions (Phase 1)
- Login does not create accounts.
- Invite onboarding is URL-token based (`/invite/:token`) and must come from admin-generated invite.
- Theme system supports dark/light modes with persisted preference in `localStorage`.
- If refresh bootstrap fails, frontend clears local auth and routes to `/login`.
- Frontend has split shells:
  - `/chat` for regular users
  - `/admin` for staff-only management operations

## App Responsibilities
- `users` owns identity, authentication flows, password changes, user search, admin user management.
- `auth_tokens` owns invite lifecycle and invite auditing.

## Non-goals in Phase 1
- No conversation/message persistence APIs yet.
- No websocket consumer yet (ticket minting only).
- No conversation UI implementation yet (chat page is placeholder).

## API Prefixes
- `/api/auth/` authentication and session lifecycle
- `/api/users/` user self/read APIs
- `/api/admin/` staff-only management APIs

## Engineering Rules
- UUID PKs where explicitly defined by models.
- Keep auth behavior centralized in `apps/users/views.py` helpers.
- Do not store refresh token in response JSON.
- Admin endpoints must remain staff-protected.
