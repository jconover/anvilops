# Contributing to AnvilOps

## Getting Started

**Prerequisites:**
- Python 3.12+
- Node 20+
- Docker + Docker Compose
- Terraform ~> 1.9.0 (for infrastructure changes)

**Setup:**
```bash
git clone https://github.com/jconover/anvilops.git
cd anvilops
cp .env.example .env
docker compose up --build
docker compose exec api alembic upgrade head
```

Backend only:
```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
```

Frontend only:
```bash
cd frontend
npm install
npm run dev   # :3000
```

## Development Workflow

**Branch naming:**
- `feature/<description>` — new functionality
- `fix/<description>` — bug fixes
- `chore/<description>` — maintenance, deps, tooling

Never commit directly to `main`. Always open a PR.

**PR process:**
1. `git checkout -b feature/<description>`
2. Make changes, run tests and lint locally
3. Push and open a PR against `main`
4. Address review feedback; squash fixups before merge

## Code Style

**Python (ruff):**
```bash
cd backend
ruff check app/           # lint
ruff format --check app/  # format check
ruff check --fix app/     # auto-fix lint issues
```
- Line length: 100 characters
- Rules enforced: `E`, `F`, `I`, `N`, `W`
- Target: Python 3.12

**Frontend (ESLint via Next.js):**
```bash
cd frontend
npm run lint
```

Match the style of surrounding code. No unused imports, no `any` casts without justification.

## Testing

**Backend (pytest, async-first):**
```bash
cd backend
pytest                        # all tests
pytest tests/test_health.py -v               # single file
pytest tests/test_health.py::test_name -v    # single test
pytest --cov=app              # with coverage
```
- All tests are `async def` — `asyncio_mode = "auto"` is set in `pyproject.toml`
- New features require tests; bug fixes should include a regression test

**Frontend (Vitest + React Testing Library):**
```bash
cd frontend
npm test         # run test suite
npm run test:ci  # non-interactive for CI
```

All PRs must have passing tests before review.

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add Windows template validation endpoint
fix: correct Celery beat schedule for drift monitor
chore: bump ruff to 0.4.x
docs: update deployment prerequisites
```

- `feat:` — new feature
- `fix:` — bug fix
- `chore:` — tooling, deps, config
- `docs:` — documentation only
- `refactor:` — no behavior change
- `test:` — test-only changes

Keep the subject line under 72 characters. Add a body if the why isn't obvious.

## Infrastructure Changes

**Terraform:**
```bash
cd terraform/platform
terraform init -backend=false
terraform validate
terraform fmt -check -recursive   # run from terraform/ root
```
Always run `validate` and review a `plan` output before opening a PR. Paste the plan summary into the PR description.

**Helm:**
```bash
helm lint helm/anvilops/
```

**In your PR description, flag:**
- Any new AWS resources or IAM permissions introduced
- Changes to secret names or ExternalSecrets references
- API version changes in K8s manifests (e.g., `v1` vs `v1beta1`)
- Naming changes between Terraform outputs and Helm/K8s manifests

## Security

- Never commit secrets, credentials, API keys, or tokens — use `.env` locally and ExternalSecrets in K8s
- No hardcoded IP addresses or AWS account IDs in source files
- Use `variables.tf` or environment-specific `tfvars` for environment-specific values
- Report vulnerabilities privately — see [SECURITY.md](SECURITY.md)

## Code Review Checklist

Before requesting review, confirm:

- [ ] Tests pass (`pytest` / `npm test`)
- [ ] Lint is clean (`ruff check app/` / `npm run lint`)
- [ ] No secrets or hardcoded values committed
- [ ] Terraform changes include `validate` output; new resources flagged in PR description
- [ ] `CLAUDE.md` updated if architecture or conventions changed
- [ ] PR description explains the *why*, not just the *what*
- All PRs require at least one approval before merging.
