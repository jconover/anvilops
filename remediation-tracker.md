# AnvilOps Security Remediation Tracker

**Created:** 2026-03-16
**Last Updated:** 2026-03-16

---

## Priority 1 — Replace Mock Auth with Real Cognito Integration

**Resolves findings:** #1, #3, #4, #5, #6
**Severity:** CRITICAL
**Status:** [x] Complete

### What to do
- [x] Remove the mock `login()` function that accepts any credentials and hardcodes `role: 'admin'`
- [x] Integrate AWS Cognito SDK (`amazon-cognito-identity-js` or `@aws-amplify/auth`) for real authentication
- [x] Roles must come from signed Cognito JWT claims (`cognito:groups`), not localStorage
- [x] Set auth cookies server-side with `Secure; HttpOnly; SameSite=Strict`
- [x] Remove `dev-token` hardcoded string and localStorage token storage

### Files to modify
- `frontend/src/lib/auth/context.tsx` — replace mock login with Cognito auth flow
- `frontend/src/lib/api/client.ts` — switch from localStorage token to cookie-based auth
- `frontend/src/lib/providers.tsx` — wire up Cognito provider

---

## Priority 2 — Add JWT Validation in Next.js Middleware

**Resolves findings:** #2, #15
**Severity:** CRITICAL
**Status:** [x] Complete

### What to do
- [x] Validate JWT signature against Cognito JWKS endpoint (use `jose` or `aws-jwt-verify`)
- [x] Verify token expiry, issuer (`iss`), and audience (`aud`)
- [x] Reject invalid/expired tokens with redirect to login
- [x] Narrow `/api` public route exemption to specific endpoints (e.g., `/api/health`)

### Files to modify
- `frontend/src/middleware.ts` — add JWT verification logic and tighten `PUBLIC_ROUTES`

---

## Priority 3 — Implement Server-Side Authorization on All Backend Endpoints

**Resolves findings:** #7, #13, #33
**Severity:** HIGH
**Status:** [x] Complete

### What to do
- [x] Create a FastAPI dependency that extracts and validates the JWT from the request
- [x] Check `cognito:groups` claim against required role for each endpoint
- [x] Return 401/403 for unauthenticated/unauthorized requests
- [x] Do not rely on Cognito OAuth scopes alone; validate group membership
- [ ] Move data-fetching in approvals page behind the permission check (page does not exist yet)

### Files to modify
- `backend/app/middleware/audit.py` — add auth extraction
- Create `backend/app/core/auth.py` — JWT validation dependency
- All route files in `backend/app/api/` — add auth dependency
- `frontend/src/app/dashboard/approvals/page.tsx` — defer data fetching until after permission check

---

## Priority 4 — Enable SSL Verification by Default

**Resolves findings:** #8, #9
**Severity:** HIGH
**Status:** [x] Complete

### What to do
- [x] Change `AWX_VERIFY_SSL` default from `False` to `True`
- [x] Change `PUPPET_VERIFY_SSL` default from `False` to `True`
- [x] Change WinRM `ansible_winrm_server_cert_validation` from `"ignore"` to `"validate"`
- [x] Update `.env.example` to show `AWX_VERIFY_SSL=true` and `PUPPET_VERIFY_SSL=true`
- [x] Wire `AWX_VERIFY_SSL` into both AWX httpx clients (was dead config — never passed to httpx)
- [x] Update `ansible/group_vars/windows.yml` WinRM cert validation to `"validate"`
- [ ] Deploy proper CA certificates to AWX for WinRM validation (infrastructure prerequisite)

### Files modified
- `backend/app/core/config.py:21,29` — flipped defaults to `True`
- `backend/app/services/awx.py:45` — WinRM cert validation changed to `"validate"`
- `backend/app/services/awx.py:91,595` — wired `verify=settings.AWX_VERIFY_SSL` into both httpx clients
- `ansible/group_vars/windows.yml:8` — WinRM cert validation changed to `"validate"`
- `.env.example:19,27` — updated example values
- `backend/tests/test_config.py` — updated assertions

---

## Priority 5 — Pin GitHub Actions to Commit SHAs

**Resolves findings:** #12, #31
**Severity:** HIGH
**Status:** [x] Complete

### What to do
- [x] Replace all `uses: actions/checkout@v4` style references with full SHA pins
- [x] Pin `lewagon/wait-on-check-action` to commit SHA (marked as third-party)
- [x] Add version comments next to SHA pins for maintainability

### Files modified
- `.github/workflows/ci.yml` — all 20 `uses:` lines pinned to commit SHAs
- `.github/workflows/deploy.yml` — all 7 `uses:` lines pinned to commit SHAs

---

## Priority 6 — Harden Backend Defaults and Middleware

**Resolves findings:** #10, #11, #18, #19
**Severity:** HIGH/MEDIUM
**Status:** [ ] Not Started

### What to do
- Restrict `ProxyHeadersMiddleware` trusted_hosts to known proxy CIDR ranges
- Remove default DB credentials (empty string, fail fast on startup)
- Add rate limiting middleware (e.g., `slowapi`)
- Restrict CORS `allow_methods` and `allow_headers` to explicit lists

### Files to modify
- `backend/app/main.py:51,57-58` — trusted_hosts, CORS config
- `backend/app/core/config.py:7` — remove default DATABASE_URL credentials

---

## Priority 7 — Add Security Headers

**Resolves findings:** #16, #17
**Severity:** MEDIUM
**Status:** [ ] Not Started

### What to do
- Add `headers()` config to `next.config.mjs` with CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy
- Validate `callbackUrl` as a relative path before redirect (reject absolute URLs, `//` prefix)

### Files to modify
- `frontend/next.config.mjs` — add `headers()` function
- `frontend/src/app/(auth)/login/page.tsx` — validate callbackUrl

---

## Priority 8 — Harden Cognito Terraform Configuration

**Resolves findings:** #23, #24, #25, #26
**Severity:** MEDIUM
**Status:** [ ] Not Started

### What to do
- Enable `advanced_security_mode = "ENFORCED"` on the user pool
- Add `validation` blocks requiring HTTPS on callback/logout URLs
- Lock `mfa_configuration` to `"ON"` only (remove `OPTIONAL`)
- Reduce refresh token validity from 30 days to 7 days

### Files to modify
- `terraform/platform/modules/cognito/main.tf` — add `user_pool_add_ons`, reduce refresh token
- `terraform/platform/modules/cognito/variables.tf` — add URL validation, lock MFA

---

## Priority 9 — Harden Kubernetes/Helm Secrets and Config

**Resolves findings:** #14, #27, #28, #29, #39
**Severity:** MEDIUM
**Status:** [ ] Not Started

### What to do
- Move ElastiCache endpoint to Secrets Manager or ConfigMap variable
- Split `anvilops-secrets` into per-component secrets (API, worker, beat)
- Change default Redis URL to `rediss://` (TLS)
- Replace placeholder Puppet secret with `random_password` resource
- Standardize ExternalSecret API version to `v1`

### Files to modify
- `terraform/platform/k8s/overlays/dev/external-secrets.yaml`
- `helm/anvilops/templates/api-deployment.yaml`
- `helm/anvilops/values.yaml`
- `terraform/platform/modules/puppet/main.tf`
- `helm/anvilops/templates/external-secrets.yaml`

---

## Priority 10 — Harden CI/CD Pipeline

**Resolves findings:** #30, #32
**Severity:** MEDIUM
**Status:** [ ] Not Started

### What to do
- Move `id-token: write` from workflow-level to only the deploy job that needs it
- Remove `latest` tag from ECR image pushes; use only immutable SHA-based tags

### Files to modify
- `.github/workflows/deploy.yml:25` — scope permissions per-job
- `.github/workflows/deploy.yml:106,121` — remove `latest` tag

---

## Priority 11 — Remaining Medium/Low Items

**Resolves findings:** #20, #21, #22, #34, #35, #36, #37, #38, #40
**Severity:** MEDIUM/LOW
**Status:** [ ] Not Started

### What to do
- Implement webhook timestamp validation in `port.py`
- Sanitize error responses to strip upstream details
- Decouple SQL echo from DEBUG flag
- Disable Swagger UI in production
- Validate X-Forwarded-For as IP format
- Add negative security tests (auth bypass, injection, malicious headers)
- Add CMK encryption to Secrets Manager secrets
- Enable Cognito event logging
- Plan CSRF protection for future cookie-based auth migration

### Files to modify
- `backend/app/services/port.py`
- `backend/app/services/puppet.py`, `awx.py`
- `backend/app/db/session.py`
- `backend/app/main.py`
- `backend/app/middleware/audit.py`
- `backend/tests/`
- `terraform/platform/modules/cognito/main.tf`
