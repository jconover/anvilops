# AWX Setup Guide

This document describes the AWX (Ansible Tower) infrastructure in AnvilOps, what is already provisioned, what prerequisites exist, and remaining gaps.

---

## 1. Infrastructure Provisioned by Terraform

All AWX resources are defined in `terraform/platform/helm/install-charts.tf`.

| Resource | Type | Description |
|---|---|---|
| `helm_release.awx_operator` | Helm chart | AWX Operator v2.19.1 in the `awx` namespace |
| `random_password.awx_admin` | Random password | 24-char admin password |
| `random_password.awx_db` | Random password | 24-char PostgreSQL password |
| `kubectl_manifest.awx_admin_password_secret` | K8s Secret | `awx-admin-password` in `awx` namespace |
| `kubectl_manifest.awx_postgres_config_secret` | K8s Secret | `awx-postgres-configuration` with RDS connection details |
| `kubectl_manifest.awx_instance` | AWX CR | AWX instance with ClusterIP service, external RDS, persistent project storage (10Gi) |
| `aws_secretsmanager_secret.awx` | Secrets Manager | `anvilops/awx` — stores URL, username, password for backend integration |
| `kubectl_manifest.awx_config_job` | K8s Job | `awx-configure` — bootstraps AWX org, project, inventories, and job templates |

**Note:** The AWX Operator values file (`awx-operator-values.yaml`) sets `AWX.enabled: false`. The AWX instance is created separately via the `awx_instance` kubectl_manifest resource using the AWX CRD, not via the operator's built-in AWX deployment.

### AWX Instance Spec (`awx-instance.yaml`)

- Service type: ClusterIP (no ingress)
- External PostgreSQL via `awx-postgres-configuration` secret
- Admin password via `awx-admin-password` secret
- Persistent project storage: 10Gi ReadWriteOnce
- Resource limits: web (1 CPU / 2Gi), task (1 CPU / 2Gi), EE (500m / 1Gi)

---

## 2. AWX Config Job

The `awx-configure` K8s Job (`terraform/platform/helm/awx-config-job.yaml`) runs after the AWX instance is ready and bootstraps:

### Organization
- **AnvilOps** — top-level organization for all automation

### Project
- Name: `${project_name}` (default: `anvilops`)
- SCM type: Git
- SCM URL: `${awx_git_repo_url}` (Terraform variable)
- Auto-update on launch: enabled

### Inventories (3)
| Inventory | Description |
|---|---|
| `anvilops-dev` | Development environment |
| `anvilops-staging` | Staging environment |
| `anvilops-production` | Production environment |

All inventories are created under the AnvilOps organization with an `environment` variable set to the environment name.

### Job Templates (8)

| Template Name | Playbook | Description |
|---|---|---|
| `anvilops-server-provisioning` | `playbooks/provision_server.yml` | Provision a new server |
| `anvilops-compliance-check` | `playbooks/compliance_check.yml` | Run compliance checks against servers |
| `anvilops-decommission` | `playbooks/decommission_server.yml` | Decommission an existing server |
| `anvilops-linux-base` | `playbooks/linux-base.yml` | Base configuration for Linux servers |
| `anvilops-windows-base` | `playbooks/windows-base.yml` | Base configuration for Windows servers |
| `anvilops-domain-join` | `playbooks/domain-join.yml` | Join server to Active Directory domain |
| `anvilops-install-software` | `playbooks/install-software.yml` | Install requested software packages |
| `anvilops-deploy-agents` | `playbooks/deploy-agents.yml` | Deploy monitoring and management agents |

All templates are configured with:
- Default inventory: `anvilops-dev`
- `ask_inventory_on_launch: true` — inventory can be overridden at launch
- `ask_variables_on_launch: true` — extra vars can be passed at launch

---

## 3. Prerequisites Before Deployment

### Required Terraform Variables
- `awx_git_repo_url` — Git repository URL for AWX project sync (the repo containing the Ansible playbooks). Currently defaults to `""`.
- `rds_endpoint` — PostgreSQL RDS endpoint for AWX's database. Defaults to `""`.

### Playbook Files That Must Exist in the Git Repo

The AWX project syncs playbooks from the git repo. The config job creates job templates pointing to these playbook paths:

| Expected Path | Exists in `ansible/playbooks/`? |
|---|---|
| `playbooks/provision_server.yml` | **MISSING** |
| `playbooks/compliance_check.yml` | **MISSING** |
| `playbooks/decommission_server.yml` | **MISSING** |
| `playbooks/linux-base.yml` | Yes |
| `playbooks/windows-base.yml` | Yes |
| `playbooks/domain-join.yml` | Yes |
| `playbooks/install-software.yml` | Yes |
| `playbooks/deploy-agents.yml` | Yes |

**Additional playbook present but not in config job:** `playbooks/puppet-bootstrap.yml` — exists in the repo but has no corresponding AWX job template.

---

## 4. Credential Flow: Secrets Manager -> ExternalSecret -> Backend

```
Terraform (install-charts.tf)
  |
  |-- aws_secretsmanager_secret.awx
  |     key: "anvilops/awx"
  |     value: { url, username, password }
  |
  v
ExternalSecret (terraform/platform/k8s/overlays/dev/external-secrets.yaml)
  |
  |-- remoteRef: key=anvilops/awx, property=password
  |     maps to: secretKey=awx_password
  |
  v
K8s Secret: "anvilops-secrets" (namespace: anvilops)
  |
  |-- AWX_PASSWORD env var
  |
  v
Backend pods (api, worker, beat deployments)
  |
  |-- app.core.config.Settings reads AWX_BASE_URL, AWX_USERNAME, AWX_PASSWORD
  |     AWX_BASE_URL default: "http://awx:8052"
  |     AWX_USERNAME default: ""
  |     AWX_PASSWORD default: ""
```

**Note:** The Terraform config job uses `http://awx-service.awx.svc.cluster.local` as the AWX URL (stored in Secrets Manager), but the backend `config.py` defaults to `http://awx:8052`. The `AWX_BASE_URL` must be set via environment variable or the ExternalSecret should also map the AWX URL. Currently only `password` is mapped from the Secrets Manager secret — `url` and `username` are not mapped to env vars.

---

## 5. Backend Integration

### Service Layer (`backend/app/services/awx.py`)

Two clients:
- **`AWXService`** (async, httpx.AsyncClient) — for FastAPI endpoints
- **`AWXServiceSync`** (sync, httpx.Client) — for Celery tasks

Both provide:
- Health check (`/api/v2/ping/`)
- Inventory management (get/create inventory, groups, hosts)
- Job template lookup by name and launch
- Job polling and stdout retrieval
- Host removal (for decommission)
- **`run_configuration_pipeline()`** — the main Day-1 orchestration method

### Configuration Pipeline (`run_configuration_pipeline`)

Called by Celery after Terraform provisions an EC2 instance:

1. Get or create inventory: `anvilops-{environment}`
2. Get or create OS group: `linux` or `windows`
3. Add host with connection variables (SSH for Linux, WinRM for Windows)
4. Resolve job templates based on server config:
   - Always: `anvilops-{os_family}-base`
   - If `domain_join=true`: `anvilops-domain-join`
   - If `software_packages` non-empty: `anvilops-install-software`
   - Always: `anvilops-deploy-agents`
5. Launch templates sequentially, polling each to completion
6. Abort pipeline on first failure

### Celery Tasks (`backend/app/tasks/awx.py`)

| Task | Celery Name | Purpose |
|---|---|---|
| `awx_configure` | `tasks.awx_configure` | Run Day-1 config pipeline, update build step status |
| `awx_decommission` | `tasks.awx_decommission` | Remove host from AWX (best-effort) |

### Orchestrator (`backend/app/tasks/orchestrator.py`)

The `run_server_build` task executes the full pipeline:
```
terraform_plan -> terraform_apply -> awx_configure -> puppet_enroll -> validation
```

- AWX runs in the **"configuring"** phase after Terraform succeeds
- On AWX failure: triggers terraform destroy rollback
- On AWX success: stores `awx_host_id` on the server request, transitions to "validating"

### Exception Hierarchy (`backend/app/services/awx_exceptions.py`)

```
AWXError (base)
  +-- AWXConnectionError  (unreachable)
  +-- AWXAuthError        (401/403)
  +-- AWXJobError         (job failed/errored/canceled)
  +-- AWXTimeoutError     (polling exceeded timeout)
```

---

## 6. Remaining TODOs and Gaps

### Missing Playbooks
- `playbooks/provision_server.yml` — referenced by `anvilops-server-provisioning` template but does not exist
- `playbooks/compliance_check.yml` — referenced by `anvilops-compliance-check` template but does not exist
- `playbooks/decommission_server.yml` — referenced by `anvilops-decommission` template but does not exist

### Unused Playbook
- `playbooks/puppet-bootstrap.yml` exists but has no AWX job template. If Puppet bootstrap should be triggered via AWX, a job template needs to be added to the config job.

### Credential Gaps
- **AWX URL mismatch:** Secrets Manager stores `http://awx-service.awx.svc.cluster.local` but backend defaults to `http://awx:8052`. The `url` field from Secrets Manager is not mapped to an env var.
- **AWX username not mapped:** Only `password` is extracted from the `anvilops/awx` Secrets Manager secret. The `username` field (`admin`) is not mapped to `AWX_USERNAME` env var.
- **No AWX credential types defined:** The config job does not create Machine credentials (SSH keys, WinRM credentials) in AWX. Without these, job templates cannot actually connect to provisioned servers.
- **No SCM credentials:** If the `awx_git_repo_url` is a private repo, SCM credentials need to be configured in AWX for project sync.

### RBAC
- No AWX users, teams, or role assignments are created by the config job. Only the `admin` user exists.
- No RBAC segregation between dev/staging/production inventories.

### Inventory Sources
- Inventories are created as static (empty). No dynamic inventory sources (e.g., AWS EC2 plugin) are configured.
- Hosts are added dynamically by the backend's `run_configuration_pipeline`, but there is no mechanism to sync or reconcile with actual AWS state.

### Config Job Limitations
- The config job is a one-shot K8s Job with `ttlSecondsAfterFinished: 600`. If it fails or AWX isn't ready within 5 minutes (30 attempts x 10s), the job fails with no automatic retry beyond `restartPolicy: OnFailure`.
- The `GRAFANA_ADMIN_PASSWORD` env var is injected but never used by the config script.
- All job templates default to the `anvilops-dev` inventory. The backend overrides this at launch time, but if someone launches manually from the AWX UI without specifying an inventory, it defaults to dev.

### Backend Integration Gaps
- The `anvilops-server-provisioning`, `anvilops-compliance-check`, and `anvilops-decommission` templates are created in AWX but are **never launched** by the backend. The backend only uses the Day-1 configuration pipeline templates (`*-base`, `domain-join`, `install-software`, `deploy-agents`).
- The `awx_decommission` Celery task removes the host from AWX inventory but does **not** launch the `anvilops-decommission` job template to run any decommission playbook.
- No mechanism to trigger `anvilops-compliance-check` or `anvilops-server-provisioning` from the backend.

### Network / Connectivity
- AWX service type is ClusterIP with no ingress. AWX UI is only accessible from within the cluster (or via port-forward).
- No configuration for AWX to reach provisioned EC2 instances (security groups, SSH keys, WinRM setup). This must be handled externally or by Terraform.
