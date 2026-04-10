# AnvilOps Security Audit Findings

**Date:** 2026-03-16
**Scope:** Authentication, authorization, and secrets management across frontend, backend, infrastructure, and CI/CD
**Auth Provider:** AWS Cognito (client-side integration)

---

## CRITICAL (Fix Before Any Deployment)

| # | Finding | File(s) |
|---|---------|---------|
| 1 | **Mock auth accepts any credentials, grants admin role** — `login()` never validates against a backend; hardcodes `role: 'admin'` for everyone | `frontend/src/lib/auth/context.tsx:48-58` |
| 2 | **Middleware only checks token presence, not validity** — `if (!token)` is the only check; any non-empty string passes | `frontend/src/middleware.ts:19-27` |
| 3 | **User role stored in tamper-accessible localStorage** — any user can edit localStorage to `"role":"admin"` and bypass all RBAC | `frontend/src/lib/auth/context.tsx:33-36` |
| 4 | **Hardcoded static `dev-token`** — shipped in source, trivially guessable | `frontend/src/lib/auth/context.tsx:55-57` |

---

## HIGH

| # | Finding | File(s) |
|---|---------|---------|
| 5 | **Auth cookie missing `Secure` and `HttpOnly` flags** — XSS can steal it; sent over plaintext HTTP | `frontend/src/lib/auth/context.tsx:57` |
| 6 | **Token in localStorage vulnerable to XSS exfiltration** | `context.tsx:54-55`, `frontend/src/lib/api/client.ts:26` |
| 7 | **All authorization is client-side only** — `RoleGate`/`AuthGuard` are React components, not security boundaries; backend has no auth middleware | `role-gate.tsx`, `auth-guard.tsx`, `backend/app/middleware/audit.py:50` |
| 8 | **SSL verification disabled by default for AWX and Puppet** — MitM exposes credentials on the wire | `backend/app/core/config.py:21,29` |
| 9 | **WinRM cert validation hardcoded to `ignore`** — MitM on Windows management traffic | `backend/app/services/awx.py:45` |
| 10 | **ProxyHeadersMiddleware trusts all hosts (`*`)** — anyone can spoof `X-Forwarded-For`, poisoning audit logs | `backend/app/main.py:51` |
| 11 | **Hardcoded default DB credentials** (`anvilops:anvilops`) — silent fallback if env var unset | `backend/app/core/config.py:7` |
| 12 | **GitHub Actions pinned to mutable tags, not SHAs** — supply chain risk | `.github/workflows/ci.yml`, `deploy.yml` (all `uses:` lines) |
| 13 | **All Cognito OAuth scopes granted to every user** — backend must validate group membership or any user gets `admin:manage` | `terraform/platform/modules/cognito/main.tf:190-198` |
| 14 | **Hardcoded ElastiCache endpoint in dev manifest** — leaks internal infra addressing | `terraform/platform/k8s/overlays/dev/external-secrets.yaml:29` |

---

## MEDIUM

| # | Finding | File(s) |
|---|---------|---------|
| 15 | **`/api` blanket-whitelisted as public route** — all Next.js API routes bypass auth | `frontend/src/middleware.ts:4` |
| 16 | **No security headers** (CSP, HSTS, X-Frame-Options) | `frontend/next.config.mjs` |
| 17 | **Potential open redirect via unvalidated `callbackUrl`** | `frontend/src/middleware.ts:25` |
| 18 | **No rate limiting on any backend endpoint** | `backend/app/main.py` |
| 19 | **CORS allows all methods and all headers** (`*`) | `backend/app/main.py:57-58` |
| 20 | [x] FIXED **Webhook timestamp replay protection declared but not implemented** — Implementation verified at `backend/app/services/port.py:100-123` (validate_webhook_timestamp) and called at `backend/app/api/v1/port.py:71` | `backend/app/services/port.py:39,60-97` |
| 21 | [x] FIXED **Error responses may leak upstream service details** (hostnames, response bodies) — Global exception handler added to `backend/app/main.py` that sanitizes upstream service errors and unhandled exceptions when DEBUG=False. Returns generic 503 for upstream errors, generic 500 for others. | `puppet.py:176`, `awx.py:135`, `port.py:169` |
| 22 | **SQL echo tied to DEBUG flag** — if DEBUG leaks to prod, all queries logged | `backend/app/db/session.py:13` |
| 23 | **No Cognito Advanced Security features** (no credential stuffing detection) | `cognito/main.tf` |
| 24 | **No HTTPS validation on Cognito callback/logout URLs** | `cognito/variables.tf:16-24` |
| 25 | **MFA can be downgraded to OPTIONAL** | `cognito/variables.tf:44-53` |
| 26 | **30-day refresh token validity** — long exposure window for infra management | `cognito/main.tf:212` |
| 27 | **All K8s secrets injected into all containers** — violates least privilege | `helm/anvilops/templates/api-deployment.yaml:54-56` |
| 28 | **Default Redis URL uses plaintext `redis://`** not `rediss://` | `helm/anvilops/values.yaml:303` |
| 29 | **Placeholder Puppet secret committed** — may never be rotated | `terraform/platform/modules/puppet/main.tf:101` |
| 30 | **`id-token: write` too broadly scoped** in deploy workflow | `.github/workflows/deploy.yml:25` |
| 31 | **Third-party action `lewagon/wait-on-check-action`** receives GITHUB_TOKEN without SHA pin | `.github/workflows/deploy.yml:37` |
| 32 | [x] FIXED **`latest` tag used for production container images** — mutable, ambiguous provenance — Deploy workflow now tags with `github.sha`; `latest` is never used in staging/production. | `.github/workflows/deploy.yml:106,121` |
| 33 | **Approvals page fetches data before permission check** — data in memory even when "Access Denied" renders | `frontend/src/app/dashboard/approvals/page.tsx:18-34` |

---

## LOW

| # | Finding | File(s) |
|---|---------|---------|
| 34 | **OpenAPI/Swagger UI exposed unconditionally** | `backend/app/main.py:41-46` |
| 35 | **X-Forwarded-For not validated as IP format** (log injection) | `backend/app/middleware/audit.py:41-44` |
| 36 | **No negative security tests** (auth bypass, injection, malicious headers) | `backend/tests/` |
| 37 | **Secrets Manager secret lacks CMK encryption** | `cognito/main.tf:229-235` |
| 38 | **No Cognito event logging configured** | `cognito/main.tf` |
| 39 | **ExternalSecret API version mismatch** (`v1beta1` vs `v1`) | Helm vs dev overlay |
| 40 | **No CSRF protection** (low risk while using Bearer header, risk increases if moving to cookies) | `frontend/src/lib/api/client.ts` |
