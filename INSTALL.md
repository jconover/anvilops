# AnvilOps Installation & Testing Guide

Complete guide for setting up, running, and testing the AnvilOps server provisioning platform locally.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Quick Start (Docker Compose)](#2-quick-start-docker-compose)
3. [Database Setup & Migrations](#3-database-setup--migrations)
4. [Running the Backend API](#4-running-the-backend-api)
5. [Running the Celery Worker](#5-running-the-celery-worker)
6. [Running the Frontend](#6-running-the-frontend)
7. [Testing the API](#7-testing-the-api)
8. [Running Automated Tests](#8-running-automated-tests)
9. [Terraform Local Testing](#9-terraform-local-testing)
10. [Ansible Local Testing](#10-ansible-local-testing)
11. [Puppet Local Testing](#11-puppet-local-testing)
12. [Slack Webhook Setup](#12-slack-webhook-setup)
13. [Environment Variables Reference](#13-environment-variables-reference)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. Prerequisites

### Required Software

| Tool | Version | Purpose |
|------|---------|---------|
| **Docker & Docker Compose** | Latest | Containerized local dev environment |
| **Python** | >= 3.12 | Backend API and Celery worker |
| **Node.js** | >= 18.x | Frontend Next.js application |
| **npm** | >= 9.x | Frontend package management |
| **Git** | Latest | Source control |

### Optional (for infrastructure testing)

| Tool | Version | Purpose |
|------|---------|---------|
| **Terraform** | >= 1.5.0 | Infrastructure provisioning testing |
| **AWS CLI** | v2 | AWS credential management |
| **Ansible** | >= 2.13 | Playbook testing without AWX |
| **Puppet Agent** | 7 or 8 | Manifest validation |
| **Ruby** | >= 2.7 | puppet-lint, r10k, rspec-puppet |

---

## 2. Quick Start (Docker Compose)

The fastest way to get the backend running locally.

### Step 1: Clone and configure

```bash
git clone https://github.com/jconover/anvilops.git
cd anvilops
cp .env.example .env
```

### Step 2: Start all services

```bash
docker compose up --build
```

This starts 4 services:

| Service | Port | Description |
|---------|------|-------------|
| **api** | 8000 | FastAPI backend with hot-reload |
| **worker** | — | Celery task worker (2 processes) |
| **db** | 5432 | PostgreSQL 16 |
| **redis** | 6379 | Redis 7 (broker + result backend) |

### Step 3: Run database migrations

```bash
docker compose exec api alembic upgrade head
```

### Step 4: Verify

```bash
curl http://localhost:8000/health
# {"status": "healthy", "service": "anvilops-api"}
```

API docs available at: **http://localhost:8000/docs**

### Step 5: Start the frontend (separate terminal)

```bash
cd frontend
npm install
npm run dev
```

Frontend available at: **http://localhost:3000**

### Docker Compose Architecture

```
                    ┌──────────────┐
                    │   Frontend   │
                    │  Next.js     │
                    │  :3000       │
                    └──────┬───────┘
                           │ /api/* proxy
                    ┌──────▼───────┐
         ┌──────────│   API        │──────────┐
         │          │  FastAPI     │          │
         │          │  :8000       │          │
         │          └──────────────┘          │
         │                                    │
    ┌────▼─────┐                      ┌──────▼───────┐
    │   db     │                      │   redis      │
    │ Postgres │                      │   Redis 7    │
    │  :5432   │                      │   :6379      │
    └──────────┘                      └──────┬───────┘
                                             │
                                      ┌──────▼───────┐
                                      │   worker     │
                                      │  Celery      │
                                      │  (2 procs)   │
                                      └──────────────┘
```

### Connecting to the containerized database

The Docker Compose stack includes PostgreSQL — no separate install needed. To connect:

```powershell
# Open a psql shell inside the running container
docker compose exec db psql -U anvilops -d anvilops
```

You'll see the `anvilops=#` prompt. From here you can inspect data:

```sql
-- List all tables
\dt

-- Check server requests
SELECT id, server_name, status, environment FROM server_requests;

-- Check migration state
SELECT * FROM alembic_version;

-- Exit
\q
```

Connection details (if you want to connect from a GUI tool like pgAdmin or DBeaver):

| Setting | Value |
|---------|-------|
| Host | `localhost` |
| Port | `5432` |
| Database | `anvilops` |
| Username | `anvilops` |
| Password | `anvilops` |

### Connecting to the containerized Redis

```powershell
# Open a redis-cli shell inside the running container
docker compose exec redis redis-cli
```

```
# Check it's alive
PING
# Returns: PONG

# See Celery queues
KEYS *

# Exit
QUIT
```

### Stopping services

```bash
docker compose down          # Stop containers
docker compose down -v       # Stop and remove volumes (resets database)
```

---

## 3. Database Setup & Migrations

### Initial migration

The project uses Alembic for database migrations with async PostgreSQL support.

```bash
cd backend

# Apply all migrations
alembic upgrade head

# Check current migration state
alembic current

# View migration history
alembic history --verbose
```

### Current migration state

The initial migration (`e50e8f1b2e9e`) creates:
- `server_requests` table — main server provisioning lifecycle
- `build_steps` table — pipeline step tracking

**Note:** Models for templates, audit logs, notifications, scaling groups, schedules, and drift events are defined in code but may need additional migrations generated:

```bash
# Generate a new migration from model changes
alembic revision --autogenerate -m "Add phase 3 and 4 models"

# Apply it
alembic upgrade head
```

### Rollback

```bash
alembic downgrade -1       # Rollback one revision
alembic downgrade base     # Rollback everything
```

### Connection details

| Context | Driver | URL Pattern |
|---------|--------|-------------|
| FastAPI (async) | asyncpg | `postgresql+asyncpg://user:pass@host:5432/db` |
| Celery (sync) | psycopg2 | Auto-converted from async URL |
| Alembic | asyncpg | Same as FastAPI |

---

## 4. Running the Backend API

### With Docker (recommended)

```bash
docker compose up api
```

The API starts with `--reload` for hot-reloading during development.

### Without Docker

```bash
cd backend
source venv/bin/activate

# Start the API server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### What happens on startup

1. FastAPI initializes with CORS middleware (all origins allowed in dev)
2. Default server templates are seeded into the database (6 templates)
3. API routes are registered under `/api/v1`
4. Health check available at `/health`

### Key URLs

| URL | Description |
|-----|-------------|
| http://localhost:8000/health | Health check |
| http://localhost:8000/docs | Swagger UI (interactive API docs) |
| http://localhost:8000/redoc | ReDoc (alternative API docs) |
| http://localhost:8000/api/v1/... | All API endpoints |

---

## 5. Running the Celery Worker

The Celery worker processes async tasks (Terraform, AWX, Puppet, notifications).

### With Docker

```bash
docker compose up worker
```

### Without Docker

```bash
cd backend
source venv/bin/activate

# Basic worker
celery -A app.worker.celery_app worker --loglevel=info

# With concurrency control
celery -A app.worker.celery_app worker --loglevel=info --concurrency=4

# Debug mode (single process, verbose)
celery -A app.worker.celery_app worker --loglevel=debug --pool=solo
```

### Worker configuration

| Setting | Value | Description |
|---------|-------|-------------|
| Broker | Redis | `REDIS_URL` env var |
| Result backend | Redis | Same as broker |
| Serializer | JSON | All messages/results |
| Ack mode | Late | Tasks ack after completion |
| Prefetch | 1 | One task per worker at a time |

### Monitoring with Flower (optional)

```bash
pip install flower
celery -A app.worker.celery_app flower --port=5555
# Visit http://localhost:5555
```

### Task inventory

| Task | Module | Purpose |
|------|--------|---------|
| `run_server_build` | orchestrator.py | Main build pipeline |
| `terraform_plan` | terraform.py | Generate Terraform plan |
| `terraform_apply` | terraform.py | Apply infrastructure |
| `terraform_destroy` | terraform.py | Destroy infrastructure |
| `awx_configure` | awx.py | Day-1 OS configuration |
| `awx_decommission` | awx.py | Remove from AWX |
| `puppet_enroll` | puppet.py | Puppet Enterprise enrollment |
| `puppet_decommission` | puppet.py | Purge from Puppet |
| `run_validation` | validation.py | Post-build health checks |
| `send_slack_notification` | notifications.py | Slack messages |
| `run_server_decommission` | decommission.py | Full teardown pipeline |
| `cmdb_sync_server` | cmdb.py | ServiceNow sync |
| `cmdb_full_sync` | cmdb.py | Full CMDB reconciliation |
| `scale_group` | scaling.py | Scale to target count |
| `check_scaling_triggers` | scaling.py | Periodic scaling eval |
| `poll_drift_events` | drift.py | PuppetDB drift polling |
| `generate_drift_report` | drift.py | Daily drift summary |
| `process_scheduled_builds` | scheduler.py | Process due schedules |
| `execute_scheduled_build` | scheduler.py | Run single scheduled build |

---

## 6. Running the Frontend

### Development server

```bash
cd frontend
npm install
npm run dev
```

Frontend available at: **http://localhost:3000**

### How it connects to the backend

The Next.js config proxies all `/api/*` requests to the backend:

```
Frontend (:3000) → /api/* → proxy → Backend (:8000)
```

The proxy target is configurable via the `NEXT_PUBLIC_API_URL` environment variable (defaults to `http://localhost:8000`).

### Authentication (development mode)

Auth is currently mocked for development:
- Any email/password combination works on the login page
- The mock user gets `admin` role by default
- Token stored in `localStorage` as `anvilops_token`

### Key frontend routes

| Route | Description |
|-------|-------------|
| `/` | Redirects to dashboard |
| `/auth/login` | Login page |
| `/dashboard` | Dashboard home with stats |
| `/dashboard/servers/new` | Server builder wizard (5 steps) |
| `/dashboard/servers` | Server inventory table |
| `/dashboard/servers/[id]` | Server detail + decommission |
| `/dashboard/requests` | Request tracker list |
| `/dashboard/requests/[id]` | Pipeline visualization |
| `/dashboard/approvals` | Approval queue (Approver/Admin) |
| `/dashboard/compliance` | Puppet compliance dashboard |
| `/dashboard/drift` | Drift detection dashboard |
| `/dashboard/scaling` | Auto-scaling groups |
| `/dashboard/schedules` | Scheduled builds |
| `/dashboard/cmdb` | ServiceNow CMDB (Admin) |
| `/dashboard/notifications` | Notification center |
| `/dashboard/audit` | Audit log (Admin) |

### Build for production

```bash
cd frontend
npm run build
npm start     # Starts production server on :3000
```

---

## 7. Testing the API

### Interactive testing

Open **http://localhost:8000/docs** for the Swagger UI where you can test all endpoints interactively.

### curl examples

#### Health check

```bash
curl http://localhost:8000/health
```

#### List regions and VPCs

```bash
# List supported regions
curl http://localhost:8000/api/v1/regions/

# List VPCs in a region
curl http://localhost:8000/api/v1/regions/us-east-1/vpcs

# List subnets in a VPC
curl http://localhost:8000/api/v1/regions/us-east-1/vpcs/vpc-12345678/subnets
```

#### List templates

```bash
curl http://localhost:8000/api/v1/templates/
```

#### Get cost estimate

```bash
curl -X POST http://localhost:8000/api/v1/costs/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "instance_size": "medium",
    "os_type": "amazon_linux_2023",
    "region": "us-east-1",
    "additional_storage": []
  }'
```

#### Create a server request

Minimal (auto-generated name):

```bash
curl -X POST http://localhost:8000/api/v1/servers/ \
  -H "Content-Type: application/json" \
  -d '{
    "environment": "dev",
    "os_type": "amazon_linux_2023",
    "instance_size": "small",
    "vpc_id": "vpc-12345678",
    "subnet_id": "subnet-87654321"
  }'
```

Full-featured Windows SQL Server:

```bash
curl -X POST http://localhost:8000/api/v1/servers/ \
  -H "Content-Type: application/json" \
  -d '{
    "server_name": "PROD-SQL-db01",
    "environment": "production",
    "os_type": "windows_2022",
    "instance_size": "large",
    "region": "us-east-1",
    "vpc_id": "vpc-12345678",
    "subnet_id": "subnet-87654321",
    "security_profile": "database",
    "domain_join": true,
    "software_packages": ["sql-server-2022"],
    "puppet_role": "db_server",
    "additional_storage": [
      {"drive_letter": "D:", "size_gb": 500, "volume_type": "io2"},
      {"drive_letter": "E:", "size_gb": 200, "volume_type": "io2"}
    ],
    "tags": {"Owner": "dba-team", "CostCenter": "database"}
  }'
```

#### List and get servers

```bash
# List all servers
curl http://localhost:8000/api/v1/servers/

# Filter by status
curl "http://localhost:8000/api/v1/servers/?status=ready"

# Get specific server (replace UUID)
curl http://localhost:8000/api/v1/servers/<server-id>
```

#### Decommission a server

```bash
curl -X POST http://localhost:8000/api/v1/servers/<server-id>/decommission
```

### End-to-end test script

```bash
#!/bin/bash
# Save as test-api.sh and run: bash test-api.sh

API="http://localhost:8000/api/v1"

echo "=== Health Check ==="
curl -s http://localhost:8000/health | python -m json.tool

echo -e "\n=== Regions ==="
curl -s "$API/regions/" | python -m json.tool

echo -e "\n=== Templates ==="
curl -s "$API/templates/" | python -m json.tool

echo -e "\n=== Cost Estimate ==="
curl -s -X POST "$API/costs/estimate" \
  -H "Content-Type: application/json" \
  -d '{"instance_size":"small","os_type":"amazon_linux_2023","region":"us-east-1","additional_storage":[]}' \
  | python -m json.tool

echo -e "\n=== Create Server ==="
RESP=$(curl -s -X POST "$API/servers/" \
  -H "Content-Type: application/json" \
  -d '{
    "environment":"dev",
    "os_type":"amazon_linux_2023",
    "instance_size":"small",
    "vpc_id":"vpc-test-123",
    "subnet_id":"subnet-test-456"
  }')
echo "$RESP" | python -m json.tool

# Extract server ID (requires jq)
# SERVER_ID=$(echo "$RESP" | jq -r '.id')
# echo -e "\n=== Get Server $SERVER_ID ==="
# curl -s "$API/servers/$SERVER_ID" | python -m json.tool

echo -e "\n=== List Servers ==="
curl -s "$API/servers/" | python -m json.tool

echo -e "\n=== Done ==="
```

### ServerCreateRequest field reference

| Field | Type | Required | Default | Allowed Values |
|-------|------|----------|---------|----------------|
| `server_name` | string | No | Auto-generated (ENV-ROLE-xxxx) | Any string |
| `environment` | string | Yes | — | `dev`, `staging`, `production` |
| `os_type` | string | Yes | — | `windows_2022`, `windows_2019`, `amazon_linux_2023`, `ubuntu_2204`, `rhel_9` |
| `instance_size` | string | Yes | — | `small`, `medium`, `large`, `xl` |
| `region` | string | No | `us-east-1` | `us-east-1`, `us-west-2` |
| `vpc_id` | string | Yes | — | Valid VPC ID |
| `subnet_id` | string | Yes | — | Valid Subnet ID |
| `security_profile` | string | No | `internal_only` | `web_facing`, `internal_only`, `database`, `custom` |
| `domain_join` | bool | No | `false` | `true`, `false` |
| `software_packages` | list | No | `[]` | List of strings |
| `puppet_role` | string | No | `base` | `base`, `web_server`, `db_server`, `app_server`, `dev_workstation` |
| `additional_storage` | list | No | `[]` | List of StorageConfig objects |
| `tags` | dict | No | `{}` | Key-value string pairs |
| `template_id` | string | No | `null` | UUID of a template |

### Instance size mapping

| Size | EC2 Type | vCPU | Memory |
|------|----------|------|--------|
| `small` | t3.medium | 2 | 4 GB |
| `medium` | t3.xlarge | 4 | 16 GB |
| `large` | m5.2xlarge | 8 | 32 GB |
| `xl` | m5.4xlarge | 16 | 64 GB |

---

## 8. Running Automated Tests

### Backend tests

```bash
cd backend
source venv/bin/activate

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=app

# Run specific test file
pytest tests/test_health.py

# Run specific test
pytest tests/test_health.py::test_health_endpoint -v
```

### Current test coverage

The project has a minimal test suite:
- `tests/conftest.py` — AsyncClient fixture using ASGI transport
- `tests/test_health.py` — Health endpoint test

### Test configuration

From `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- Tests are async-first using `pytest-asyncio`
- The test client calls FastAPI directly (no HTTP server needed)
- Tests use the same database configured in `.env`

### Adding new tests

Create test files in `backend/tests/`. Example API test:

```python
# backend/tests/test_servers.py
import pytest


@pytest.mark.asyncio
async def test_create_server(client):
    response = await client.post("/api/v1/servers/", json={
        "environment": "dev",
        "os_type": "amazon_linux_2023",
        "instance_size": "small",
        "vpc_id": "vpc-test-123",
        "subnet_id": "subnet-test-456",
    })
    assert response.status_code == 202
    data = response.json()
    assert data["environment"] == "dev"
    assert data["status"] == "pending"
    assert data["server_name"].startswith("DEV-")


@pytest.mark.asyncio
async def test_list_servers(client):
    response = await client.get("/api/v1/servers/")
    assert response.status_code == 200
    data = response.json()
    assert "servers" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_list_templates(client):
    response = await client.get("/api/v1/templates/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_cost_estimate(client):
    response = await client.post("/api/v1/costs/estimate", json={
        "instance_size": "medium",
        "os_type": "amazon_linux_2023",
        "region": "us-east-1",
        "additional_storage": [],
    })
    assert response.status_code == 200
```

### Linting

```bash
cd backend

# Run ruff linter
ruff check .

# Auto-fix issues
ruff check --fix .
```

Ruff is configured for Python 3.12, 100-char line length, with E/F/I/N/W rules.

### Frontend linting

```bash
cd frontend
npm run lint
```

---

## 9. Terraform Local Testing

### Prerequisites

```bash
# Verify Terraform installation
terraform version   # Needs >= 1.5.0

# Configure AWS credentials (choose one method)
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_DEFAULT_REGION=us-east-1

# OR use AWS CLI profile
export AWS_PROFILE=your-profile
```

### Module structure

```
terraform/
├── modules/           # 6 reusable modules
│   ├── ec2-linux/
│   ├── ec2-windows/
│   ├── security-group/
│   ├── iam-role/
│   ├── ebs-volumes/
│   └── dns-record/
├── environments/      # 3 environment configs
│   ├── dev/
│   ├── staging/
│   └── production/
└── templates/         # 6 pre-built .tfvars
    ├── web-server.tfvars
    ├── public-web-server.tfvars
    ├── db-server.tfvars
    ├── app-server.tfvars
    ├── app-server-java.tfvars
    └── dev-workstation.tfvars
```

### Testing with local state (no S3 backend)

```bash
cd terraform/environments/dev

# Initialize with local state (bypasses S3 requirement)
terraform init -reconfigure -backend=false

# Or use a local backend override
terraform init -reconfigure -backend-config="path=./terraform.tfstate"
```

### Validate and plan

```bash
# Edit terraform.tfvars with real VPC/subnet IDs
# Then validate
terraform validate

# Plan (dry run)
terraform plan -var-file=terraform.tfvars -input=false

# Plan with a template
terraform plan -var-file=../../templates/web-server.tfvars -input=false
```

### Apply and destroy

```bash
# Create resources
terraform apply -auto-approve -var-file=terraform.tfvars -input=false

# View outputs
terraform output -json

# Tear down
terraform destroy -auto-approve -var-file=terraform.tfvars -input=false
```

### Workspace isolation (how the backend does it)

```bash
# Create a workspace for a server
terraform workspace new server-test-001
terraform workspace select server-test-001

# Apply within workspace
terraform apply -auto-approve -var-file=terraform.tfvars

# Clean up
terraform destroy -auto-approve -var-file=terraform.tfvars
terraform workspace select default
terraform workspace delete server-test-001
```

### How the backend invokes Terraform

The `TerraformService` class (`backend/app/services/terraform.py`):

1. Sets `TF_IN_AUTOMATION=1` to disable interactive prompts
2. Runs `terraform init -input=false -no-color`
3. Creates/selects workspace `server-{request_id}`
4. Generates `.tfvars` from server request data
5. Runs `terraform plan` then `terraform apply -auto-approve`
6. Parses outputs (instance_id, private_ip, public_ip, dns_name)
7. On failure: runs `terraform destroy` for rollback

---

## 10. Ansible Local Testing

### Prerequisites

```bash
# Install Ansible
pip install ansible>=2.13

# Install required collections
cd ansible
ansible-galaxy install -r requirements.yml

# Verify
ansible --version
ansible-galaxy collection list
```

### Required collections

| Collection | Version | Purpose |
|------------|---------|---------|
| amazon.aws | >= 7.0.0 | EC2 inventory, AWS modules |
| community.general | >= 9.0.0 | General utilities |
| community.windows | >= 2.0.0 | Windows modules |
| microsoft.ad | >= 1.5.0 | Active Directory |
| ansible.windows | >= 2.0.0 | Core Windows modules |
| chocolatey.chocolatey | >= 1.5.0 | Windows packages |

### Playbook inventory

The project includes:
- **6 playbooks**: linux-base, windows-base, domain-join, install-software, deploy-agents, puppet-bootstrap
- **6 roles**: common, linux-hardening, windows-hardening, iis, sql-server, monitoring
- **Dynamic inventory**: `inventories/aws_ec2.yml` (discovers EC2 by `ManagedBy=AnvilOps` tag)

### Testing playbooks locally

```bash
cd ansible

# Syntax check
ansible-playbook playbooks/linux-base.yml --syntax-check

# Dry run against a host
ansible-playbook playbooks/linux-base.yml \
  -i "10.0.1.42," \
  --check \
  -e "ansible_user=ec2-user" \
  -e "ansible_ssh_private_key_file=~/.ssh/your-key.pem"

# Run against dynamic AWS inventory
ansible-playbook playbooks/linux-base.yml \
  -i inventories/aws_ec2.yml \
  --limit env_dev \
  -v
```

### AWX integration

The backend communicates with AWX via REST API. AWX settings:

| Setting | Default | Env Var |
|---------|---------|---------|
| Base URL | http://localhost:8052 | `AWX_BASE_URL` |
| Username | admin | `AWX_USERNAME` |
| Password | password | `AWX_PASSWORD` |
| Job timeout | 600s | `AWX_JOB_TIMEOUT` |
| Poll interval | 10s | `AWX_POLL_INTERVAL` |

AWX is not included in Docker Compose. For full integration testing, deploy AWX separately (e.g., via Kubernetes operator on EKS).

---

## 11. Puppet Local Testing

### Prerequisites

```bash
# Install Puppet agent (for parser/lint)
# See https://puppet.com/docs/puppet/latest/install_puppet.html

# Install validation tools
gem install puppet-lint r10k
```

### Validate manifests

```bash
# Syntax check all manifests
find puppet -name "*.pp" -exec puppet parser validate {} \;

# Style check
puppet-lint puppet/manifests/
puppet-lint puppet/site-modules/role/manifests/
puppet-lint puppet/site-modules/profile/manifests/
```

### Install Forge modules

```bash
# Validate Puppetfile syntax
r10k puppetfile check --puppetfile puppet/Puppetfile

# Download all module dependencies
r10k puppetfile install --puppetfile puppet/Puppetfile --moduledir puppet/modules/
```

### Validate Hiera data

```bash
# Check YAML syntax for all Hiera files
for f in puppet/data/**/*.yaml puppet/data/*.yaml; do
  ruby -e "require 'yaml'; YAML.load_file('$f')" && echo "OK: $f" || echo "FAIL: $f"
done
```

### Puppet module structure

```
puppet/
├── Puppetfile              # 20+ Forge module dependencies
├── hiera.yaml              # 5-level Hiera hierarchy
├── environment.conf        # Module path configuration
├── manifests/site.pp       # Default node classification
├── data/                   # Hiera data
│   ├── common.yaml         # Universal baseline
│   ├── environment/        # dev.yaml, staging.yaml, production.yaml
│   └── os/                 # windows.yaml, RedHat.yaml, Debian.yaml
└── site-modules/
    ├── role/               # 5 roles: base, web_server, app_server, db_server, dev_workstation
    └── profile/            # 14+ profiles: base, security, compliance, monitoring, etc.
```

### Puppet Enterprise integration

The backend communicates with PE via REST APIs. PE settings:

| Setting | Default | Env Var |
|---------|---------|---------|
| Base URL | https://puppet.anvilops.internal | `PUPPET_BASE_URL` |
| API Token | (empty) | `PUPPET_API_TOKEN` |
| Verify SSL | false | `PUPPET_VERIFY_SSL` |
| Classifier port | 4433 | `PUPPET_CLASSIFIER_PORT` |
| PuppetDB port | 8081 | `PUPPET_PUPPETDB_PORT` |
| Orchestrator port | 8143 | `PUPPET_ORCHESTRATOR_PORT` |
| CA port | 8140 | `PUPPET_CA_PORT` |

PE is not included in Docker Compose. For full integration testing, deploy Puppet Enterprise separately (trial license supports 10 nodes).

---

## 12. Slack Webhook Setup

AnvilOps sends Slack notifications for build events, approval requests, and compliance alerts. This requires a Slack incoming webhook and optionally a Slack app for interactive approval buttons.

### Step 1: Create a Slack App

1. Go to **https://api.slack.com/apps** and click **Create New App**
2. Select **From scratch**
3. Name it `AnvilOps` (or any name) and pick your workspace
4. Click **Create App**

### Step 2: Enable Incoming Webhooks

1. In your app settings, go to **Features > Incoming Webhooks**
2. Toggle **Activate Incoming Webhooks** to **On**
3. Click **Add New Webhook to Workspace**
4. Select the channel you want notifications in (e.g. `#anvilops-builds`)
5. Click **Allow**
6. Copy the **Webhook URL** — it looks like:
   ```
   https://hooks.slack.com/services/TXXXXX/BXXXXX/XXXXXXXXXX
   ```

### Step 3: Configure environment variables

Add these to your `.env` file:

```env
SLACK_ENABLED=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/TXXXXX/BXXXXX/XXXXXXXXXX
SLACK_CHANNEL=#anvilops-builds
SLACK_APP_URL=http://localhost:3000
```

| Variable | Description |
|----------|-------------|
| `SLACK_ENABLED` | Set to `true` to activate notifications |
| `SLACK_WEBHOOK_URL` | The webhook URL from Step 2 |
| `SLACK_CHANNEL` | Channel name (for display purposes in messages) |
| `SLACK_APP_URL` | Base URL of the AnvilOps frontend (used in "View Details" links) |

### Step 4: Verify the webhook

Restart the backend (or Docker Compose) so it picks up the new env vars, then test with curl:

```bash
curl -X POST "$SLACK_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{"text": "AnvilOps webhook test - working!"}'
```

You should see the message appear in your Slack channel.

### Notification types

Once configured, AnvilOps sends these notifications automatically:

| Event | Trigger | Color |
|-------|---------|-------|
| Build started | Server request begins provisioning | Blue |
| Build completed | Server reaches "ready" status | Green |
| Build failed | Any pipeline step fails | Red |
| Approval requested | Production or XL instance submitted | Yellow |
| Approval granted | Approver approves the request | Green |
| Approval rejected | Approver rejects the request | Red |
| Decommission started | Server teardown begins | Orange |
| Decommission completed | Server fully decommissioned | Gray |

### (Optional) Enable interactive approval buttons

For approve/reject buttons directly in Slack messages, you need a full Slack app with interactivity enabled.

#### Step A: Enable Interactivity

1. In your Slack app settings, go to **Features > Interactivity & Shortcuts**
2. Toggle **Interactivity** to **On**
3. Set the **Request URL** to your backend's Slack endpoint:
   ```
   https://your-domain.com/api/v1/slack/interactions
   ```
   For local development with a tunnel (e.g. ngrok):
   ```
   https://your-ngrok-id.ngrok.io/api/v1/slack/interactions
   ```
4. Click **Save Changes**

#### Step B: Get the Signing Secret

1. Go to **Settings > Basic Information**
2. Under **App Credentials**, find **Signing Secret**
3. Copy it and add to `.env`:
   ```env
   SLACK_SIGNING_SECRET=
   ```

The backend uses this secret to verify that incoming requests to `/api/v1/slack/interactions` actually come from Slack (HMAC-SHA256 signature verification).

#### Step C: Expose your local backend (for development)

Slack needs a public URL to send interactive callbacks to. Use ngrok or a similar tunnel:

```bash
# Install ngrok: https://ngrok.com/download
ngrok http 8000
```

Copy the `https://` forwarding URL and paste it as the Request URL in Step A.

#### Step D: Test the flow

1. Create a production server request via the API or frontend
2. AnvilOps sends an approval message to Slack with Approve/Reject buttons
3. Click a button in Slack
4. Slack sends the action to `/api/v1/slack/interactions`
5. The backend processes the action and updates the Slack message

### Notifications without Slack

If Slack is disabled (`SLACK_ENABLED=false`, the default), the system still works — all build events generate in-app notifications visible at `/dashboard/notifications`. Slack is supplemental, not required.

---

## 13. Environment Variables Reference

Create a `.env` file in the project root. All variables with defaults:

### Core Services

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://anvilops:anvilops@localhost:5432/anvilops` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis broker/backend |
| `DEBUG` | `false` | Enable debug logging |
| `API_V1_PREFIX` | `/api/v1` | API route prefix |
| `PROJECT_NAME` | `AnvilOps` | Application name |

### AWS / Terraform

| Variable | Default | Description |
|----------|---------|-------------|
| `TERRAFORM_WORK_DIR` | `/tmp/terraform` | Terraform working directory |
| `AWS_DEFAULT_REGION` | `us-east-1` | Default AWS region |
| `AWS_ACCESS_KEY_ID` | (empty) | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | (empty) | AWS credentials |

### AWX / Ansible

| Variable | Default | Description |
|----------|---------|-------------|
| `AWX_BASE_URL` | `http://localhost:8052` | AWX REST API URL |
| `AWX_USERNAME` | `admin` | AWX auth username |
| `AWX_PASSWORD` | `password` | AWX auth password |
| `AWX_VERIFY_SSL` | `false` | SSL verification |
| `AWX_JOB_TIMEOUT` | `600` | Job wait timeout (seconds) |
| `AWX_POLL_INTERVAL` | `10` | Job status poll interval (seconds) |
| `AWX_ORGANIZATION_ID` | `1` | AWX organization ID |

### Puppet Enterprise

| Variable | Default | Description |
|----------|---------|-------------|
| `PUPPET_BASE_URL` | `https://puppet.anvilops.internal` | PE server URL |
| `PUPPET_API_TOKEN` | (empty) | PE RBAC API token |
| `PUPPET_VERIFY_SSL` | `false` | SSL verification |
| `PUPPET_CA_PORT` | `8140` | Certificate Authority port |
| `PUPPET_CLASSIFIER_PORT` | `4433` | Node Classifier port |
| `PUPPET_PUPPETDB_PORT` | `8081` | PuppetDB port |
| `PUPPET_ORCHESTRATOR_PORT` | `8143` | Orchestrator port |
| `PUPPET_NODE_CHECKIN_TIMEOUT` | `600` | Node checkin timeout (seconds) |
| `PUPPET_NODE_CHECKIN_POLL` | `30` | Checkin poll interval (seconds) |
| `PUPPET_DEFAULT_ENVIRONMENT` | `production` | Default Puppet environment |
| `PUPPET_CERTNAME_DOMAIN` | `anvilops.internal` | Domain for cert names |

### Slack

| Variable | Default | Description |
|----------|---------|-------------|
| `SLACK_WEBHOOK_URL` | (empty) | Slack incoming webhook URL |
| `SLACK_SIGNING_SECRET` | (empty) | Slack app signing secret |
| `SLACK_ENABLED` | `false` | Enable Slack notifications |
| `SLACK_CHANNEL` | `#anvilops-builds` | Default Slack channel |
| `SLACK_APP_URL` | `http://localhost:3000` | App URL for Slack links |

### ServiceNow CMDB

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVICENOW_INSTANCE_URL` | (empty) | ServiceNow instance URL |
| `SERVICENOW_USERNAME` | (empty) | ServiceNow API username |
| `SERVICENOW_PASSWORD` | (empty) | ServiceNow API password |
| `SERVICENOW_ENABLED` | `false` | Enable CMDB sync |
| `SERVICENOW_TABLE` | `cmdb_ci_server` | CMDB table name |

### Frontend

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API URL for proxy |

---

## 14. Troubleshooting

### Docker Compose issues

**Database not ready:**
```
sqlalchemy.exc.OperationalError: connection refused
```
The API waits for the database health check, but migrations may not have run. Execute:
```bash
docker compose exec api alembic upgrade head
```

**Port conflicts:**
```
Error: port 8000 already in use
```
Stop any existing services or change ports in `docker-compose.yml`.

**Reset everything:**
```bash
docker compose down -v    # Remove containers and volumes
docker compose up --build # Rebuild from scratch
```

### Migration issues

**Tables missing for Phase 3/4 models:**
```
sqlalchemy.exc.ProgrammingError: relation "server_templates" does not exist
```
Generate and apply new migrations:
```bash
cd backend
alembic revision --autogenerate -m "Add all models"
alembic upgrade head
```

**Migration conflict:**
```bash
alembic current            # Check current state
alembic history --verbose  # View all revisions
alembic stamp head         # Force-mark current state (use carefully)
```

### Celery worker issues

**Worker not picking up tasks:**
- Verify Redis is running: `redis-cli ping`
- Check `REDIS_URL` matches between API and worker
- Restart the worker after code changes

**Task import errors:**
- Ensure all task modules exist in `backend/app/tasks/`
- Check `celery_app.autodiscover_tasks(["app.tasks"])` configuration

### Frontend issues

**API calls returning 404:**
- Verify the backend is running on port 8000
- Check `NEXT_PUBLIC_API_URL` is set correctly
- Confirm the Next.js proxy rewrite in `next.config.ts`

**Login not working:**
- Auth is mocked in development. Any email/password works.
- If redirected to login repeatedly, clear localStorage: `localStorage.clear()`

### Terraform issues

**State backend not accessible:**
For local testing, bypass the S3 backend:
```bash
terraform init -reconfigure -backend=false
```

**AWS credentials missing:**
```
Error: No valid credential sources found
```
Set `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`, or configure `AWS_PROFILE`.
