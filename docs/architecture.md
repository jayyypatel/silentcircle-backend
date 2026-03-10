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
1. User completes invite or logs in.
2. Backend issues access token in response body.
3. Backend issues refresh token in `HttpOnly` cookie.
4. Client sends `Authorization: Bearer <access>` for protected endpoints.
5. Client refreshes access token via `/api/auth/token/refresh/` using cookie.
6. For websocket bootstrap, client requests `/api/auth/ws-ticket/`; server stores one-time ticket in Redis (`ws_ticket:<uuid>`, 30s TTL).

## App Responsibilities
- `users` owns identity, authentication flows, password changes, user search, admin user management.
- `auth_tokens` owns invite lifecycle and invite auditing.

## Non-goals in Phase 1
- No conversation/message persistence APIs yet.
- No websocket consumer yet (ticket minting only).
- No frontend implementation tracked in this repo.

## API Prefixes
- `/api/auth/` authentication and session lifecycle
- `/api/users/` user self/read APIs
- `/api/admin/` staff-only management APIs

## Engineering Rules
- UUID PKs where explicitly defined by models.
- Keep auth behavior centralized in `apps/users/views.py` helpers.
- Do not store refresh token in response JSON.
- Admin endpoints must remain staff-protected.
