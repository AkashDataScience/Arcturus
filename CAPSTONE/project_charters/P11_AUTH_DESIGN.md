# P11 Auth Design — Login & Authentication

**Purpose:** Design document for auth (user registration, login, guest experience, and migration). Share with the team for review.

**Related:** user_id FE ownership; Phase 5 Lifecycle and Shared Space.

---

## 1. Context & Goals

### 1.1 Current State
- `user_id` is created and cached in `memory/remme_index/user_id.json` on the backend.
- `get_user_id()` in `memory/user_id.py` is used across remme, runs, qdrant_store, memory_retriever, sync engine.
- No login or registration. Backend cannot be deployed separately from FE or used as a multi-tenant app.

### 1.2 Target State
- Registration and login on the frontend to create/identify users.
- User model persisted in a database.
- Guest experience preserved (no registration required).
- Backend `get_user_id()` kept but implemented to resolve identity from Security Context (JWT or headers).
- Guest data migrated to the registered user when they register or login.
- Spaces: guest users create only `local_only` spaces; these migrate as-is and never sync.

---

## 2. User Model & Storage

### 2.1 User Model (DB)

| Field | Type | Notes |
|-------|------|-------|
| `id` (user_id) | UUID | Primary key; tenant isolation everywhere |
| `email` | string | Unique; null for guest |
| `password_hash` | string | bcrypt/argon2; null for guest |
| `auth_type` | enum | `guest` \| `registered` |
| `migrated_guest_ids` | list[UUID] | Guest IDs already merged into this account |
| `created_at` | datetime | |
| `updated_at` | datetime | |

- **Guest**: `auth_type=guest`, `email=null`, `password_hash=null`, `id` = guest UUID.
- **Registered**: `auth_type=registered`, `email` and `password_hash` set.
- **migrated_guest_ids**: Tracks which guest IDs have been merged (for idempotency across devices).

### 2.2 Storage
- **SQLite** (using SQLAlchemy or SQLModel) is the strictly recommended default for user/auth. It requires zero configuration, works instantly for local/self-hosted users, and keeps the deployment footprint small.
- Neo4j remains for graph data; user/auth in relational DB.

---

## 3. Authentication Flows

### 3.1 Identity Flows
| Flow | Description |
|------|-------------|
| **Guest** | FE generates UUID (or calls `/auth/guest`), persists in `localStorage`, sends as `X-User-Id` on every request. |
| **Register** | POST `/auth/register` with email + password. Optional `guest_id` for merge. Returns JWT. |
| **Login** | POST `/auth/login` with email + password. Optional `guest_id` for merge. Returns JWT. |
| **Token** | JWT contains `user_id`; validated by middleware; identity available via `get_user_id()`. |

### 3.2 Identity Resolution Order (Backend)
1. Valid JWT → `user_id` from token payload.
2. `X-User-Id` header (valid UUID) → guest/fallback when no JWT.
3. No auth, no header → 401 for protected routes. **All Mnemo data routes** (`/runs`, `/remme/*`, `/api/sync/*`) are protected and MUST have either a valid JWT `Authorization` header OR an `X-User-Id` guest header.

---

## 4. Multi-Device Guest → Registered Scenario

**Important:** Login and Register both trigger migration. Multiple devices can produce multiple guest IDs over time.

### 4.1 Scenario
1. **Device A – Guest**: User does runs, creates memories as `guest_A`.
2. **Device A – Register**: User registers → migrate `guest_A` → `registered_user_id`. All Device A data under the account.
3. **Device B – New Guest**: Next day, different device. No prior identity → new `guest_B`. User does runs and memories.
4. **Device B – Login**: User logs in → migrate `guest_B` → `registered_user_id`. Device B data is now part of the same account.

### 4.2 Migration Rules
- **Register**: Accept `guest_id` (current device) and merge into new registered user.
- **Login**: Accept `guest_id` (current device) and merge into existing registered user.
- **migrated_guest_ids**: Before migrating, check if `guest_id` is already in the list → no-op if yes. After successful migration → append `guest_id`.
- **Idempotency**: Same guest logging in again (e.g., logout/login) → no re-migration.
- **Multiple devices**: Each device has its own guest ID; each login/register can merge that device’s guest data.

### 4.3 Migration Service Responsibilities
Reassign all data from `source_guest_id` to `target_user_id`:
- Ensure the backend migration logic is wrapped in a **transaction** (for SQL/Neo4j) to prevent partial migrations.
- **Qdrant**: Update payload `user_id` for points owned by guest.
- **Neo4j**: Update User node and relationships (User–HAS_MEMORY, HAS_FACT, Sessions, Spaces, etc.). Note: `user_id` must also be updated directly on `Fact` nodes, as they store it locally per the schema.
- **Sync logs**: Update `user_id` in sync log entries.
- **Session summaries**: Update user-scoped files if any.

---

## 5. Backend: get_user_id() and Security Context

### 5.1 Principle
- Keep `get_user_id()` as the single entry point for callers (no API change).
- Implementation resolves identity in order: Security Context → `X-User-Id` header → legacy file fallback.

### 5.2 Request-Scoped Context
- Use Python `contextvars` for per-request `user_id`.
- Auth middleware: validate JWT, set `_request_user_id`; else read `X-User-Id`, validate UUID, set context.
- `get_user_id()` reads from context; falls back to header; then legacy file-based id for backward compatibility.

### 5.3 Store Changes
- QdrantStore and others should call `get_user_id()` per operation rather than caching at init.
- Ensures multi-tenant behavior when context is set per request.

---

## 6. Frontend

### 6.1 Identity State
- **Guest**: `{ user_id }` in `localStorage`.
- **Logged-in**: `{ user_id, email, token }`.
- API client sends `X-User-Id` on all requests; `Authorization: Bearer <token>` when logged in.

### 6.2 Guest Creation
- **FE Ownership**: The frontend generates the UUID using `crypto.randomUUID()` and stores it in `localStorage`. This avoids an unnecessary round-trip to the server and aligns with the frontend ownership goal.

### 6.3 Login/Register UX
- Prompt: "Merge this device’s data into your account?" Yes → send `guest_id` with request. No → start fresh.
- Sync Enablement Prompt (post-login/register): "Would you like to enable cloud sync for your existing spaces?" Yes → update `sync_policy` of newly-migrated spaces to `sync`.

---

## 7. Spaces (Guest Rules)

- Guest users create only `sync_policy=local_only` spaces.
- On migration, spaces remain `local_only` (no automatic sync).
- `local_only` spaces never sync (consistent with Sync Engine design).

---

## 8. API Contract

### 8.1 New Endpoints
| Method | Path | Body | Purpose |
|--------|------|------|---------|
| POST | `/auth/register` | `{ email, password, guest_id? }` | Register; merge guest if `guest_id` provided |
| POST | `/auth/login` | `{ email, password, guest_id? }` | Login; merge guest if `guest_id` provided |
| GET | `/auth/guest` | — | Optional; returns new guest `user_id` |
| GET | `/auth/me` | — | Current user (requires valid token) |

### 8.2 Headers
| Header | Purpose |
|--------|---------|
| `Authorization: Bearer <jwt>` | Authenticated requests |
| `X-User-Id: <uuid>` | Guest identity or fallback; validated UUID |

---

## 9. Security Considerations

- Store passwords with bcrypt or Argon2.
- Rate-limit login/register.
- Use **long-lived JWTs** (e.g., 30 days); secret from env. This provides a better UX for a personal memory app without the complexity of refresh tokens.
- Validate `X-User-Id` format (UUID); do not use for authorization.
- Enforce HTTPS in production.

---

## 10. Implementation Order

1. User model + DB migrations.
2. Auth endpoints (register, login, optional guest, `/auth/me`).
3. JWT validation middleware + `contextvars` for request-scoped identity.
4. Refactor `get_user_id()`: context → header → legacy fallback.
5. Wire stores/retrievers to use `get_user_id()` per request.
6. FE: identity slice, API headers, localStorage.
7. FE: login/register UI.
8. Migration service: guest → registered data merge.
9. Spaces: enforce `local_only` for guests.
10. Sync engine: bind to authenticated `user_id`.

---

## 11. Backward Compatibility

- Feature flag: `AUTH_ENABLED=true` to enable JWT and header-based identity.
- When disabled or no identity in context: `get_user_id()` falls back to file-based `user_id.json` (single-tenant, dev).
- Existing scripts and callers continue to use `get_user_id()` unchanged.

---

## 12. Out of Scope (This Phase)

- OAuth/social login
- Email verification
- MFA
- Password reset
- Refresh token rotation
- Admin user management UI

---

## 13. Production: Moving from HS256 to RS256

**Current implementation:** JWT is signed with **HS256** and a single shared secret (`MNEMO_SECRET_KEY`). This is simple and fine for single-server or dev; the same server that issues the token also verifies it using the same secret.

**For production (multi-server, or separation of issuer vs verifier):** It is **recommended to move to RS256** (or ES256). With RS256:

- **Asymmetric keys:** Only the **auth server** holds the **private key** and signs tokens. Other services (e.g. API servers, sync servers) only need the **public key** to verify; they cannot issue tokens. Compromise of one service does not allow forging JWTs.
- **Key configuration:**
  - **Private key:** Used by the process that implements login/register (e.g. `routers/auth.py`). Store in env (e.g. `MNEMO_JWT_PRIVATE_KEY`) or in a secret manager. Format: PEM (e.g. PKCS#8 or PKCS#1). Never expose to clients or to services that only verify.
  - **Public key:** Used by any process that only verifies tokens (middleware, other microservices). Can be in env (`MNEMO_JWT_PUBLIC_KEY`) or fetched from a well-known JWKS URL. PEM or JWKS format.
- **Algorithm:** Set `ALGORITHM = "RS256"`. Encode with private key; decode with public key. PyJWT supports both: `jwt.encode(..., key=private_key, algorithm="RS256")` and `jwt.decode(..., key=public_key, algorithms=["RS256"])`.
- **Key generation (example):**
  ```bash
  # Private key (keep secret)
  openssl genrsa -out private.pem 2048
  # Public key (can be shared with verifiers)
  openssl rsa -in private.pem -pubout -out public.pem
  ```
  Then set `MNEMO_JWT_PRIVATE_KEY` to the contents of `private.pem` (or path) and `MNEMO_JWT_PUBLIC_KEY` to the contents of `public.pem` for verifier processes.
- **Migration path:** Support both HS256 and RS256 during rollout: e.g. read `MNEMO_SECRET_KEY` for HS256 if present, else use `MNEMO_JWT_PRIVATE_KEY` / `MNEMO_JWT_PUBLIC_KEY` for RS256. Once all issuers use RS256, deprecate HS256.

**Summary:** For production, use RS256 with a dedicated private key for signing and a public key for verification; configure keys via env or secret manager and never commit them.

---

## 14. Future Enhancements and Improvements

- **RS256 rollout:** Implement and document RS256 as above; add optional JWKS endpoint for public key distribution.
- **Refresh tokens:** Optional short-lived access token + refresh token for tighter security without sacrificing UX.
- **OAuth / social login:** Allow sign-in with Google/GitHub etc.; map to same user model and migration flow where applicable.
- **MFA and password reset:** Add when required by policy or compliance.

---

**Related:** P11_SYNC_ENGINE_DESIGN.md (sync auth), P11_DELIVERY_README.md (Phase 5 scope).
