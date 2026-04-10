# Puppet Enterprise Setup Guide

This document describes the Puppet Enterprise (PE) infrastructure provisioned by AnvilOps, how it integrates with the platform, and what prerequisites and ongoing operational tasks are required.

---

## 1. Infrastructure Overview

The Puppet module (`terraform/platform/modules/puppet/`) provisions the following AWS resources:

| Resource | Purpose |
|---|---|
| **EC2 Instance** (`r5.xlarge` default) | Runs Puppet Enterprise (monolithic install) |
| **EBS Volume** (200 GB gp3) | Mounted at `/opt/puppetlabs` for PE data persistence |
| **Secrets Manager** — console password | Auto-generated 24-char admin password stored as `{project}-{env}-puppet-console-*` |
| **Secrets Manager** — API token | PE RBAC token written by user_data after install, stored as `anvilops/puppet` |
| **Route 53 A Record** (optional) | `puppet.{domain_name}` pointing to the instance private IP |
| **CloudWatch Log Groups** (4) | `puppet-server`, `puppet-console`, `puppetdb`, `system` logs |
| **SSM Parameter** | CloudWatch Agent configuration at `/anvilops/{env}/puppet/cloudwatch-agent-config` |

The instance is placed in the first private subnet, uses IMDSv2 (tokens required), and has encrypted root (100 GB) and data volumes.

## 2. PE Installation (user_data Script)

The bootstrap script (`templates/user_data.sh.tftpl`) runs 9 steps on first boot:

1. **Hostname** — Sets `puppet.{domain_name}` and updates `/etc/hosts`
2. **EBS mount** — Waits for `/dev/xvdf`, formats if new, mounts to `/opt/puppetlabs`, adds to fstab
3. **Prerequisites** — Installs curl, wget, tar, jq, etc. (yum or apt)
4. **Console password** — Retrieves from Secrets Manager via AWS CLI
5. **PE install** — Downloads tarball from `pm.puppet.com`, detects OS platform (AL2023 maps to `el-9`), generates `pe.conf`, runs `puppet-enterprise-installer`
6. **Post-install** — Writes autosign.conf, runs first Puppet agent, deploys code via Code Manager (if `puppet_code_repo_url` is set)
7. **API token** — Waits for RBAC API readiness, generates a 1-year token via `/rbac-api/v1/auth/token`, stores it in Secrets Manager
8. **CloudWatch agent** — Installs and configures from SSM Parameter
9. **Finalize** — Enables PE services, writes bootstrap-complete marker

The full bootstrap log is written to `/var/log/puppet-bootstrap.log`.

## 3. Prerequisites

### Required before `terraform apply`

| Prerequisite | How to provide | Notes |
|---|---|---|
| **VPC + private subnets** | Created by the networking module | Instance goes in `private_subnet_ids[0]` |
| **Security group** | `module.networking.puppet_security_group_id` | Must allow inbound 8140 (agent), 8081 (PuppetDB), 4433 (classifier/RBAC), 8143 (orchestrator) from EKS/VPC |
| **IAM instance profile** | `module.iam.puppet_instance_profile_name` | Needs: Secrets Manager read/write, SSM GetParameter, CloudWatch Logs/Metrics, EC2 describe |
| **Private hosted zone** (optional) | `var.private_hosted_zone_id` | For `puppet.{domain}` DNS record; skip by leaving empty |
| **SSH key pair** (optional) | `var.ssh_key_name` | For direct SSH; leave empty to use SSM Session Manager only |

### Required for full functionality (not enforced by Terraform)

| Prerequisite | Variable | Impact if missing |
|---|---|---|
| **Puppet code Git repo** | `var.puppet_code_repo_url` | Code Manager/r10k will have nothing to deploy; nodes get empty catalogs |
| **Deploy key / SSH key for code repo** | Manual setup on PE server | Code Manager cannot clone without credentials |
| **AMI compatibility** | `var.puppet_ami_id` (default: latest AL2023) | PE 2023.8 requires RHEL-family or Ubuntu; AL2023 maps to `el-9` packages |

## 4. Code Manager / r10k Configuration

Code Manager is auto-configured during PE installation via `pe.conf`:

```json
{
  "puppet_enterprise::profile::master::code_manager_auto_configure": true,
  "puppet_enterprise::profile::master::r10k_remote": "<puppet_code_repo_url>"
}
```

After installation, the user_data script runs:
```bash
/opt/puppetlabs/bin/puppet-code deploy --all --wait
```

**Expected Puppet code repository structure** (roles & profiles pattern):
```
control-repo/
  Puppetfile           # Module dependencies for r10k
  environment.conf
  hiera.yaml           # Hiera hierarchy
  data/                # Hiera data (YAML)
  site-modules/
    role/
      manifests/
        base.pp
        web_server.pp
        db_server.pp
        app_server.pp
        dev_workstation.pp
    profile/
      manifests/
        base.pp        # Common baseline profile
        ...
  manifests/
    site.pp            # Main site manifest
```

The roles must match `ROLE_CLASS_MAP` in `backend/app/services/puppet_classifier.py`:
- `base` -> `role::base`
- `web_server` -> `role::web_server`
- `db_server` -> `role::db_server`
- `app_server` -> `role::app_server`
- `dev_workstation` -> `role::dev_workstation`

## 5. API Token Generation and Storage

The PE RBAC API token is generated automatically during bootstrap:

1. The user_data script waits for the RBAC API (`https://puppet.{domain}:4433/rbac-api/v1/auth/token`) to respond with HTTP 200 or 401
2. Authenticates with the admin user and the auto-generated console password
3. Requests a token with `"lifetime": "1y"`
4. Stores it in Secrets Manager at `anvilops/puppet` as `{"api_token": "<token>"}`

Terraform pre-creates the secret with a placeholder value and uses `lifecycle { ignore_changes = [secret_string] }` so subsequent applies don't overwrite the real token.

**The AnvilOps backend** reads this token via `PUPPET_API_TOKEN` environment variable (see `backend/app/core/config.py`). This must be populated from the Secrets Manager secret in the Kubernetes deployment (Helm values or ExternalSecret).

### Token renewal

The token expires after 1 year. Renewal requires:
1. SSH/SSM into the PE server
2. Generate a new token via the RBAC API or `puppet-access` CLI
3. Update the Secrets Manager secret
4. Restart the AnvilOps backend pods to pick up the new token

## 6. Backend Integration with Puppet

### Architecture

```
AnvilOps Backend (EKS)
  |
  |-- PuppetEnterpriseService (async, for FastAPI endpoints)
  |-- PuppetEnterpriseServiceSync (sync, for Celery tasks)
  |
  +--> PE APIs (ports 4433, 8081, 8140, 8143)
         |
         +-- Node Classifier API (4433) -- /classifier-api/v1/
         +-- PuppetDB API (8081) -- /pdb/query/v4/
         +-- Orchestrator API (8143) -- /orchestrator/v1/
         +-- RBAC API (4433) -- /rbac-api/v1/
         +-- Puppet CA API (8140) -- /puppet-ca/v1/
```

Authentication: All requests use `X-Authentication: <RBAC token>` header.

### Configuration (`backend/app/core/config.py`)

| Setting | Default | Description |
|---|---|---|
| `PUPPET_BASE_URL` | `https://puppet:8140` | PE server base URL |
| `PUPPET_API_TOKEN` | (empty) | RBAC API token from Secrets Manager |
| `PUPPET_VERIFY_SSL` | `false` | SSL verification (PE uses self-signed certs) |
| `PUPPET_CA_PORT` | 8140 | Certificate Authority API |
| `PUPPET_CLASSIFIER_PORT` | 4433 | Node Classifier + RBAC API |
| `PUPPET_PUPPETDB_PORT` | 8081 | PuppetDB queries |
| `PUPPET_ORCHESTRATOR_PORT` | 8143 | On-demand Puppet runs |
| `PUPPET_NODE_CHECKIN_TIMEOUT` | 600 | Seconds to wait for first Puppet run |
| `PUPPET_NODE_CHECKIN_POLL` | 30 | Poll interval for node check-in |
| `PUPPET_CERTNAME_DOMAIN` | `anvilops.internal` | Domain suffix for certnames |

### Key services

| Module | Purpose |
|---|---|
| `services/puppet.py` | Core PE client — node classification, PuppetDB queries, cert lifecycle, orchestrator, enrollment pipeline, node purge |
| `services/puppet_classifier.py` | Maps AnvilOps `puppet_role` to PE node groups and classes |
| `services/puppet_reports.py` | Compliance aggregation — per-node and fleet-wide compliance, drift detection |
| `services/puppet_exceptions.py` | Custom exception hierarchy (connection, auth, classification, timeout) |
| `tasks/puppet.py` | Celery tasks: `puppet_enroll` and `puppet_decommission` |
| `api/v1/puppet.py` | REST endpoints: node status, reports, facts, compliance summary |
| `api/v1/compliance.py` | REST endpoints: fleet compliance summary, per-node compliance, drift reports, audit export |

### Server model fields (`models/server.py`)

| Column | Type | Set by |
|---|---|---|
| `puppet_role` | `String(64)`, default `"base"` | User at request time |
| `puppet_certname` | `String(256)`, nullable | `puppet_enroll` task |
| `puppet_node_group_id` | `String(64)`, nullable | `puppet_enroll` task |
| `puppet_last_report_status` | `String(32)`, nullable | `puppet_enroll` task |
| `puppet_enrolled_at` | `DateTime`, nullable | `puppet_enroll` task |

## 7. Day 2+ Operations: Server Registration

The provisioning pipeline (`tasks/orchestrator.py`) follows this sequence:

```
terraform_plan -> terraform_apply -> awx_configure -> puppet_enroll -> validation
```

The `puppet_enroll` Celery task:

1. Loads the server request from the database
2. Generates certname: `{server_name.lower()}.anvilops.internal`
3. Calls `PuppetEnterpriseServiceSync.enroll_node()` which:
   - Creates or finds the PE node group for the role (e.g., "AnvilOps - role::web_server")
   - Pins the node to the group
   - Signs the node's certificate (if pending)
   - Waits for the first Puppet run to appear in PuppetDB (up to 600s)
4. Stores `puppet_certname`, `puppet_node_group_id`, and `puppet_enrolled_at` on the server request

**Prerequisite**: The AWX configure step must install the Puppet agent on the target server and point it at `puppet.{domain_name}`. The agent will submit a certificate signing request (CSR) which PE auto-signs via `autosign.conf`.

### Decommission

The `puppet_decommission` task (called during server teardown):
- Looks up `puppet_certname` on the server request
- Calls `PuppetEnterpriseServiceSync.purge_node()` which deactivates the node in PuppetDB, unpins it from the classifier, and revokes/deletes the certificate
- Best-effort: failures are logged but don't block the decommission workflow

## 8. Remaining TODOs and Gaps

### Critical (required for end-to-end)

| Gap | Impact | Action needed |
|---|---|---|
| **Puppet code repository** | `puppet_code_repo_url` defaults to empty; Code Manager has nothing to deploy | Create a control repo with roles & profiles matching `ROLE_CLASS_MAP` |
| **Deploy key for code repo** | Code Manager cannot clone the repo without SSH credentials | Add deploy key to PE server and configure in PE console |
| **AWX playbook for Puppet agent install** | AWX must install and configure the Puppet agent before enrollment | Ensure the AWX job template includes puppet-agent installation pointing at `puppet.{domain}` |
| **PUPPET_API_TOKEN injection** | Backend needs the token from Secrets Manager | Wire Secrets Manager -> K8s Secret -> Helm values / ExternalSecrets operator |
| **Network connectivity** | EKS pods must reach PE on ports 4433, 8081, 8140, 8143 | Verify security group rules allow EKS cluster SG -> Puppet SG on these ports |

### Important (Day 2 readiness)

| Gap | Impact | Action needed |
|---|---|---|
| **Hiera data structure** | No environment/role-specific configuration without Hiera | Design Hiera hierarchy in the control repo (e.g., `data/roles/%{puppet_role}.yaml`) |
| **Node classification strategy** | Only 5 roles defined; no custom parameters | Extend `ROLE_CLASS_MAP` as new server types are added; consider Hiera for parameterization |
| **Token renewal automation** | 1-year token expiry requires manual renewal | Implement a Lambda or cron job to rotate the token and update Secrets Manager |
| **PE backup/restore** | No backup strategy for PuppetDB, certificates, or configs | Implement EBS snapshots or PE's built-in backup/restore |
| **PE upgrades** | `pe_version` is baked into user_data; no upgrade path defined | Document PE upgrade procedure (in-place `puppet-enterprise-installer` with new tarball) |
| **Monitoring/alerting** | CloudWatch collects logs and basic metrics but no alerts defined | Add CloudWatch alarms for PE service health, disk usage, certificate expiry |

### Nice to have

| Gap | Impact | Action needed |
|---|---|---|
| **Custom facts** | No AnvilOps-specific facts on managed nodes | Add a custom fact (e.g., `anvilops_server_id`, `anvilops_role`) via the Puppet agent |
| **PE HA** | Single PE server is a SPOF | Consider PE HA (compile masters, PuppetDB replicas) for production |
| **Reporting webhook** | PE report processor could push events to AnvilOps | Configure a custom report processor to POST to the AnvilOps compliance API |

## 9. Security Considerations

### Autosign Policy

The current autosign configuration is **domain-based wildcard**:

```
*.{domain_name}
```

This means **any host** with a FQDN matching `*.{domain_name}` will have its certificate automatically signed. This is acceptable for development but poses risks in production:

**Risks:**
- Any machine in the VPC that can reach port 8140 and present a matching certname gets a signed certificate
- A compromised host could impersonate another node's certname

**Recommendations:**
- **Production**: Replace wildcard autosign with policy-based autosign using a custom autosign script that validates a shared secret or challenge password embedded in the CSR's `challengePassword` attribute
- Consider using PE's built-in task-based provisioning or the `autosign-validator` gem for challenge-based signing

### Certificate Management

- PE manages its own CA; all agent certificates are signed by the PE CA
- Certificate revocation happens during decommission via `puppet_decommission` task
- The PE CA certificate is self-signed — `PUPPET_VERIFY_SSL` defaults to `false` in the backend
- **Recommendation**: Distribute the PE CA cert to the backend and enable SSL verification in production

### API Token Security

- The RBAC token has full admin privileges (generated with the admin account)
- Token is stored in Secrets Manager (encrypted at rest)
- **Recommendation**: Create a dedicated RBAC user with minimal permissions (node classifier read/write, PuppetDB query, orchestrator run, cert sign/revoke) instead of using the admin token

### Network Security

- PE instance is in a private subnet (no public IP)
- Access is via Security Group rules and optionally SSM Session Manager
- IMDSv2 is enforced (http_tokens = "required")
- All EBS volumes are encrypted
