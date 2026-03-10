# SilentCircle Database Model Notes (Phase 1)

## Engine and Extensions
- Engine: PostgreSQL
- Required Supabase extensions:
  - `pgcrypto`
  - `pg_trgm`

## Core Models

### `users` table (`apps.users.User`)
- PK: `id` UUID
- Identity: `username` (unique), `display_name`
- Crypto pubkeys: `x25519_public_key`, `ed25519_public_key`
- Flags: `is_active`, `is_staff`
- Relationships: `invited_by -> users.id` (nullable, self FK)
- Audit: `last_seen`, `created_at`, `updated_at`
- Indexes: `username`

### `invite_tokens` table (`apps.auth_tokens.InviteToken`)
- PK: `id` UUID
- Token: `token` unique
- FKs:
  - `created_by -> users.id`
  - `assigned_to -> users.id`
  - `used_by -> users.id` (nullable)
- Lifecycle: `expires_at`, `used_at`, `created_at`
- Helper property: `is_valid == (used_at is null && expires_at > now)`
- Indexes: `token`, `expires_at`, `used_at`

## JWT Blacklist Tables
Used from `rest_framework_simplejwt.token_blacklist`:
- `token_blacklist_outstandingtoken`
- `token_blacklist_blacklistedtoken`

These are required for logout, token rotation invalidation, and change-password invalidation.

## Migration Order Guidance
1. `users` initial migration must exist before auth token model migration.
2. `auth_tokens` migration depends on custom user model.
3. Avoid changing `AUTH_USER_MODEL` after first production migration.

## Query Conventions
- User search: case-insensitive username contains, active-only, exclude requester, limit 10.
- Admin lists: explicit ordering by `created_at` descending.
