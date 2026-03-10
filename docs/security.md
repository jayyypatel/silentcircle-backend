# SilentCircle Security Baseline (Phase 1)

## Authentication Model
- Access token: JWT returned in response body.
- Refresh token: JWT stored in `HttpOnly` cookie only.
- Refresh rotation: enabled.
- Blacklist-after-rotation: enabled.

## Password Handling
- Django password hashers prioritize Argon2.
- Password change requires old password verification.
- Password change blacklists all outstanding refresh tokens.

## Invite Security
- Invite token is high-entropy URL-safe secret.
- Invite validate endpoint does not consume token.
- Invite complete endpoint atomically:
  - verifies token validity,
  - sets credentials and public keys,
  - marks invite as used.

## Cookie Security
Defaults via env:
- `HttpOnly=true`
- `Secure=true` in base/prod, overridden to `false` in development default
- `SameSite=Lax`
- controlled max-age and path

## WebSocket Bootstrap Security
- WS auth ticket endpoint requires valid access JWT.
- Ticket is one-time and short-lived in Redis:
  - key: `ws_ticket:<uuid>`
  - value: `user_id`
  - TTL: 30 seconds

## Authorization Rules
- Default DRF permission is authenticated.
- Public endpoints are explicitly marked `AllowAny`.
- Admin endpoints require `is_staff` through custom permission.

## Logging and Data Exposure Rules
- Do not log plaintext passwords, JWTs, refresh cookies, or raw invite tokens.
- Do not log encrypted message payloads in future realtime/message endpoints.
- Error messages should stay generic for credential failures.

## Operational Security Checklist
- Set strong `DJANGO_SECRET_KEY` and `JWT_SIGNING_KEY` (32+ chars recommended for HS256).
- Keep `.env` out of version control.
- Use HTTPS in non-local environments.
- Ensure Supabase network and DB credentials are scoped minimally.
