# 🔒 SilentCircle
### *A Zero-Knowledge Server Messaging Platform*
### Privacy-first encrypted messaging — Architecture v2.0
> Architecture v2.0 — The server is a blind relay. Always.
> *"Private conversations should stay private."*

---

## 🧭 What is this?

SilentCircle is an **invite-only**, **end-to-end encrypted** messaging platform. The server is a dumb relay — it stores only encrypted blobs and has zero ability to read any message. Ever.

---

## 🎯 Four Unbreakable Rules

🔐 **E2EE always** — messages are encrypted on your device before leaving  
🙈 **Zero-knowledge server** — backend holds no keys, sees no plaintext  
🚫 **No data collection** — no IP logs, no tracking, no analytics  
✨ **Invisible security** — users never touch a key or think about crypto  

---

## ⚙️ Stack at a Glance

| Layer | Tools |
|---|---|
| 🖥️ Frontend | React 18, Zustand, libsodium, TailwindCSS |
| ⚙️ Backend | Django 4, DRF, Django Channels, Daphne |
| 🗄️ Database | Supabase PostgreSQL + Redis |
| 🔐 Crypto | X25519, AES-256-GCM, Ed25519, Argon2id |
| 🚀 Hosting | Vercel (FE) · Railway (BE) |

---

## 👤 Admin Powers

Admins manage users but **can never read messages** — enforced at the architecture level, not just policy.

✅ Create accounts · Generate invites · Deactivate users · Manage groups  
🚫 Read messages · Access private keys · Decrypt anything · Impersonate users  

---

## 🔑 How Auth Works

**First login (invite flow)**
```
Invite link → Set password → Browser generates X25519 + Ed25519 keypair
→ Private key encrypted with Argon2id(password) → stored in localStorage
→ Public keys uploaded to server → JWT issued → you're in
```

**Every login after**
```
Enter password → Decrypt private key from localStorage
→ Keys live in memory only (gone when tab closes)
→ WS ticket fetched → WebSocket opened → chats loaded
```

> 💡 Access token in memory (15 min). Refresh token in `httpOnly` cookie (7 days). Auto-refreshes silently.

> ⚠️ **New device?** No key found → modal warning. New keypair generated. Old messages unreadable on this device.

---

## 🏗️ Architecture Flow

```
[ Browser ]  →  encrypted payload only  →  [ Django + Channels ]
                                                      ↓
                                              [ Redis layer ]
                                                      ↓
                                          [ PostgreSQL / Supabase ]
                                         (stores ciphertext blobs)
```

REST handles auth, history, user lookup. WebSocket handles live delivery, typing, presence, read receipts.

---

## 🔐 Message Lifecycle

```
1. You type       →  plaintext in browser memory only
2. Key exchange   →  your privkey × their pubkey = shared secret
3. Encrypt        →  AES-256-GCM + random nonce + Ed25519 signature
4. Send           →  { ciphertext, nonce, signature } over WebSocket
5. Server         →  stores blob, routes to recipient — sees nothing
6. Recipient      →  verify sig → derive shared secret → decrypt → display
```

---

## 🖥️ Screens

| # | Screen | Route | Notes |
|---|--------|-------|-------|
| 1 | Invite Registration | `/invite/:token` | Password strength bar, keypair setup |
| 2 | Login | `/login` | Generic errors, no "forgot password" |
| 3 | Chat | `/chat` | 3-col layout, previews show `[Encrypted]` |
| 4 | New Chat | modal | `Ctrl+K`, live username search |
| 5 | Settings | `/settings` | Display name, password change, theme |
| 6 | Admin Panel | `/admin-panel` | Staff only — user & invite management |

**Delivery ticks:** 🕐 sending → `✓` sent → `✓✓` delivered → `✓✓` 🔵 read

---

## 🗄️ Core Tables

`users` — id, username, display_name, x25519_public_key, ed25519_public_key, is_staff, last_seen  
`invite_tokens` — token, created_by, assigned_to, expires_at, used_at  
`conversations` — id, type (private/group), created_by, updated_at  
`messages` — encrypted_payload, nonce, signature, sequence_number, sender_id  

---

## ⚡ WebSocket Events

| Event | Direction | What it does |
|-------|-----------|--------------|
| `send_message` | Client → Server | Sends encrypted payload |
| `receive_message` | Server → Client | Delivers to recipient |
| `message_ack` | Server → Sender | Confirms save + returns seq_num |
| `read_receipt` | Server → Sender | Blue ticks |
| `typing_start/stop` | Both | Ephemeral, Redis TTL 5s, not stored |

---

## 💡 Planned Improvements

🔄 **Double Ratchet** — forward secrecy, new key per message *(Phase 3)*  
📦 **Prekey Bundles** — message offline users without live key exchange *(Phase 2)*  
🌱 **Seed Phrase Recovery** — BIP39 backup so device loss ≠ message loss  
👆 **Key Fingerprints** — short hash for out-of-band MITM verification  

---

## 🗺️ Roadmap

| Phase | Focus | Highlights |
|-------|-------|------------|
| 🟣 Phase 1 | Auth & Identity | Invite flow, keypair gen, JWT, WS tickets |
| 🟢 Phase 2 | Messaging Core | E2EE send/receive, Channels, optimistic UI |
| 🟡 Phase 3 | Polish | Admin panel, settings, read receipts, audit |
| 🔴 Phase 4 | Rich Comms | WebRTC calls, file sharing, Double Ratchet |

---

## ❓ Open Questions

1. **Key recovery** — seed phrase support, or accept key loss on new device?
2. **Deletion policy** — soft delete (keep ciphertext) or hard delete + GDPR?
3. **Admin password reset** — forces keypair reset, old messages lost. Warn users.
4. **Group encryption** — per-recipient blobs (stronger) or shared group key (simpler)?
5. **Multi-device** — allowed for MVP, full sync is Phase 3+

---

*SilentCircle Architecture v2.0 · MVP Complete*
