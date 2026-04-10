# Terraform / K8s Change Audit

**Date:** 2026-03-07
**Scope:** Current uncommitted changes across 4 files

## Files Reviewed

1. `terraform/platform/helm/awx-config-job.yaml`
2. `terraform/platform/main.tf`
3. `terraform/platform/variables.tf`
4. `terraform/platform/k8s/overlays/dev/kustomization.yaml`

---

## Findings

### 1. ISSUE — Unused `GRAFANA_ADMIN_PASSWORD` env var in awx-config-job.yaml

**Severity:** Medium (unnecessary secret exposure)
**Location:** `terraform/platform/helm/awx-config-job.yaml:165-166`

The container defines an environment variable `GRAFANA_ADMIN_PASSWORD` with value `${grafana_admin_password}`, but **neither the shell script nor the Python code inside the job references this env var**. The AWX config script only uses `${awx_admin_password}` (injected directly by Terraform `templatefile()`). The Grafana password is exposed as a container env var for no reason.

**Recommendation:** Remove the `env:` block entirely (lines 164-166), or if Grafana password is needed for a future AWX credential, add the code that actually uses it.

### 2. ISSUE — `puppet_code_repo_url` variable in wrong section of variables.tf

**Severity:** Low (cosmetic / organizational)
**Location:** `terraform/platform/variables.tf:248-254`

The `puppet_code_repo_url` variable is declared under the `# Helm Charts` section header, but it is passed to `module "puppet"` in `main.tf:242`, not to `module "helm_charts"`. This is misleading for anyone reading the variables file.

**Recommendation:** Move the `puppet_code_repo_url` variable declaration to the `# Puppet Enterprise` section (after `puppet_ami_id`, around line 228).

---

## Confirmed Correct

### Terraform Variable Wiring (`puppet_code_repo_url`)
- Declared in `variables.tf` as `string` with default `""` — matches puppet module's declaration
- Passed through `main.tf` line 242: `puppet_code_repo_url = var.puppet_code_repo_url`
- Puppet module (`modules/puppet/variables.tf:42`) accepts it as `string` with default `""` — types match
- Used in `modules/puppet/templates/user_data.sh.tftpl` for r10k configuration and `modules/puppet/main.tf` — fully wired

### AWX Config Job — New Job Templates
- 5 new job templates (linux-base, windows-base, domain-join, install-software, deploy-agents) added correctly
- Naming pattern consistent: `{proj_name}-<template-name>`
- Playbook paths follow existing convention: `playbooks/<name>.yml`
- YAML syntax is valid
- Template structure matches existing entries (name, description, playbook fields)

### Kustomization Changes
- Comment block moved from between HPA patch and config patch to above `patches:` — no functional change
- Image tags updated from `80c1977` to `eabf082` (matches latest commit on main) — correct
- All patch targets verified against base manifests:
  - `Deployment/anvilops-api` — exists in `base/api-deployment.yaml`
  - `Deployment/anvilops-worker` — exists in `base/worker-deployment.yaml`
  - `Deployment/anvilops-frontend` — exists in `base/frontend-deployment.yaml`
  - `HorizontalPodAutoscaler/anvilops-api-hpa` — exists in `base/hpa.yaml`
  - `ConfigMap/anvilops-config` — exists in `base/configmap.yaml`
  - `ServiceAccount/anvilops-api` — exists in `base/service-accounts.yaml`
  - `ServiceAccount/anvilops-worker` — exists in `base/service-accounts.yaml`
  - `Ingress/anvilops-ingress` — exists in `base/ingress.yaml`
- IAM ARN format (`arn:aws:iam::457780993905`) is valid — IAM is a global service so the region field is empty

### AWX Admin Password Usage
- `${awx_admin_password}` is injected via `templatefile()` from `random_password.awx_admin.result`
- Used correctly in both the shell healthcheck block (line 23) and Python awxkit block (line 49)
- No mismatch between Terraform template variables and script usage
