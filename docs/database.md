# SilentCircle Database Model Notes (Phase 2)

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

### `friend_requests` table (`apps.conversations.FriendRequest`)
- PK: `id` UUID
- FKs:
  - `from_user -> users.id`
  - `to_user -> users.id`
- Status: `pending | accepted | rejected | cancelled`
- Timestamps: `created_at`, `updated_at`
- Constraints:
  - unique directional pair (`from_user`, `to_user`)
- Indexes:
  - `(to_user, status, -created_at)`
  - `(from_user, status, -created_at)`

### `friendships` table (`apps.conversations.Friendship`)
- PK: `id` UUID
- Canonical pair:
  - `user_low -> users.id`
  - `user_high -> users.id`
- Unique across unordered pair via canonical ordering.
- Timestamp: `created_at`

### `conversations` table (`apps.conversations.Conversation`)
- PK: `id` UUID
- `type` in Phase 2: `private`
- FK: `created_by -> users.id` (nullable set-null)
- Timestamps: `created_at`, `updated_at`
- Indexes: `-updated_at`, `(type, -updated_at)`

### `conversation_members` table (`apps.conversations.ConversationMember`)
- PK: `id` UUID
- FKs:
  - `conversation -> conversations.id`
  - `user -> users.id`
- Timestamp: `joined_at`
- Constraints:
  - unique pair (`conversation`, `user`)
- Indexes:
  - `user`
  - `conversation`

### `messages` table (`apps.messages.Message`)
- PK: `id` UUID
- FKs:
  - `conversation -> conversations.id`
  - `sender -> users.id` (nullable set-null)
  - `recipient -> users.id` (nullable set-null)
- Encrypted content:
  - `encrypted_payload`, `nonce`, `signature`
- Ordering:
  - `sequence_number` (server-assigned per conversation+recipient)
- Delivery tracking:
  - `delivered_at`, `created_at`
- Constraints:
  - unique (`conversation`, `recipient`, `sequence_number`)
- Indexes:
  - (`conversation`, `recipient`, `-sequence_number`)
  - `sender`
  - `recipient`

### `message_reads` table (`apps.messages.MessageRead`)
- PK: default bigint
- FKs: `message -> messages.id`, `user -> users.id`
- Timestamp: `read_at`
- Constraint: unique (`message`, `user`)

## JWT Blacklist Tables
Used from `rest_framework_simplejwt.token_blacklist`:
- `token_blacklist_outstandingtoken`
- `token_blacklist_blacklistedtoken`

These are required for logout, token rotation invalidation, and change-password invalidation.

## Migration Order Guidance
1. `users` initial migration must exist before models that reference users.
2. `auth_tokens` depends on custom user model.
3. `conversations` before `messages` due FK dependency.
4. Avoid changing `AUTH_USER_MODEL` after first production migration.

## Query Conventions
- User search: case-insensitive username contains, active-only, exclude requester, limit 10.
- Friend lists/requests: explicit status filtering and descending create order.
- Message history: recipient-scoped only, ordered by descending sequence number.
