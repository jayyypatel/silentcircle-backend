# SilentCircle Backend Architecture

## Purpose
This document is the canonical high-level context for AI-assisted backend work.
If code generation conflicts with this doc, update this doc first or fix the generation.

## Tech Stack
- Framework: Django + Django REST Framework
- Auth: `djangorestframework-simplejwt` with blacklist enabled
- Realtime: Channels + Redis (ticket auth + direct chat events)
- Database: PostgreSQL (Supabase)

## Project Structure
- `silentcircle/settings/`: split settings (`base`, `development`, `production`)
- `apps/users/`: custom user model, auth API, admin API, search API
- `apps/auth_tokens/`: invite token model and admin
- `apps/conversations/`: friendship graph + private conversation APIs
- `apps/messages/`: recipient-scoped history + read API
- `apps/realtime/`: WS middleware + chat consumer

## Runtime Flow (Phase 2)
1. Admin creates an invite for a pre-created user.
2. User completes invite or logs in.
3. Backend issues access token in response body.
4. Backend issues refresh token in `HttpOnly` cookie.
5. Client sends `Authorization: Bearer <access>` for protected endpoints.
6. Client refreshes access token via `/api/auth/token/refresh/` using cookie.
7. Client bootstraps session on app load by attempting refresh first, then `/api/users/me/`.
8. Users can only start 1:1 chat after friendship acceptance (`/api/friends/*`).
9. Client requests `/api/auth/ws-ticket/`; server stores one-time ticket in Redis (`ws_ticket:<uuid>`, 30s TTL).
10. WebSocket connects at `/ws/chat/?ticket=<uuid>`, then handles `send_message`, typing, delivery, read-receipt events.

## App Responsibilities
- `users` owns identity, authentication flows, password changes, user search, admin user management.
- `auth_tokens` owns invite lifecycle and invite auditing.
- `conversations` owns friend requests, friendships, and private conversation lifecycle.
- `messages` owns encrypted message history and read markers.
- `realtime` owns one-time WS ticket auth and realtime event routing.

## Scope Guard
- Phase 2 is private 1:1 chat only.
- Group chat is out of scope.
- Friendship acceptance is required before conversation creation.

## API Prefixes
- `/api/auth/` authentication and session lifecycle
- `/api/users/` user self/read APIs
- `/api/admin/` staff-only management APIs
- `/api/friends/` request/accept/reject/cancel/list friendship APIs
- `/api/conversations/` private conversation + message APIs

## Engineering Rules
- UUID PKs where explicitly defined by models.
- Keep auth behavior centralized in `apps/users/views.py` helpers.
- Do not store refresh token in response JSON.
- Admin endpoints must remain staff-protected.
- Message APIs must remain recipient-scoped for history reads.
- Realtime handlers must validate conversation membership and friendship before persisting/sending.
