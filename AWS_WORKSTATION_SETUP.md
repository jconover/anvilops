# AWS Workstation Setup & Team Collaboration

How to set up a new workstation (macOS, Linux, or WSL2) to work with an existing AnvilOps deployment, and how Terraform state locking works when multiple engineers share the same infrastructure.

---

## Prerequisites

| Tool | macOS | Linux (Ubuntu/Debian) |
|------|-------|-----------------------|
| AWS CLI v2 | `brew install awscli` | [AWS install guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |
| Terraform >= 1.11 | `brew install terraform` | [HashiCorp install guide](https://developer.hashicorp.com/terraform/install) |
| kubectl | `brew install kubectl` | `sudo snap install kubectl --classic` |
| Helm 3 | `brew install helm` | `sudo snap install helm --classic` |
| Git | `brew install git` | `sudo apt install git` |

Verify versions:

```bash
aws --version          # >= 2.x
terraform -version     # >= 1.11.0
kubectl version --client
helm version
```

---

## 1. Configure AWS Credentials

```bash
aws configure
# AWS Access Key ID:     <your-key>
# AWS Secret Access Key: <your-secret>
# Default region name:   us-east-1
# Default output format: json
```

Verify access:

```bash
aws sts get-caller-identity
```

---

## 2. Clone the Repository

```bash
git clone https://github.com/jconover/anvilops.git
cd anvilops
```

---

## 3. Create Local Terraform Variables

The `terraform.dev.tfvars` file is gitignored (it contains your Route 53 zone ID and IP). Create it from the example:

```bash
cd terraform/platform
cp terraform.dev.tfvars.example terraform.dev.tfvars
```

Edit `terraform.dev.tfvars` and fill in:

```hcl
# Your domain and hosted zone
domain_name              = "anvilops.example.com"
existing_route53_zone_id = ""  # e.g., "Z0123456789ABCDEFGHIJ"

# Your public IP — run: curl -s ifconfig.me
eks_enable_public_endpoint = true
eks_public_access_cidrs    = ["YOUR_IP/32"]
```

---

## 4. Initialize Terraform (Connect to Existing State)

This does **not** re-create anything — it simply connects your local Terraform to the existing state in S3:

```bash
cd terraform/platform
terraform init \
  -backend-config="bucket=anvilops-terraform-state-dev-ACCOUNT_ID" \
  -backend-config="key=platform/terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="use_lockfile=true"
```

Verify the state loaded:

```bash
terraform state list | head -20
```

---

## 5. Add Your IP to the EKS Allowlist

If your IP is different from the one already in the EKS public access CIDRs, plan and apply:

```bash
terraform plan -var-file terraform.dev.tfvars -out tfplan
terraform apply tfplan
```

This updates the EKS public endpoint CIDR allowlist. The cluster update takes 2-5 minutes.

---

## 6. Connect kubectl

```bash
aws eks update-kubeconfig --name anvilops-dev --region us-east-1
kubectl get nodes
```

Expected output:

```
NAME                          STATUS   ROLES    AGE   VERSION
ip-10-0-xx-xx.ec2.internal   Ready    <none>   ...   v1.xx
ip-10-0-xx-xx.ec2.internal   Ready    <none>   ...   v1.xx
```

### WSL2 DNS Troubleshooting

If kubectl fails with `no such host` on WSL2, the default DNS resolver (`10.255.255.254`) may not forward correctly:

```bash
# Test with Google DNS
nslookup $(kubectl config view -o jsonpath='{.clusters[0].cluster.server}' | sed 's|https://||;s|:.*||') 8.8.8.8

# If that works, fix WSL2 DNS
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf

# Permanent fix — create /etc/wsl.conf:
[network]
generateResolvConf = false
```

---

## 7. Continue with Helm Deployment

```bash
# Add required Helm repos
helm repo add external-secrets https://charts.external-secrets.io
helm repo update

# Install external-secrets (if not already installed)
helm install external-secrets external-secrets/external-secrets \
  -n external-secrets --create-namespace --set installCRDs=true --wait

# Deploy AnvilOps application stack
cd helm/anvilops
helm dependency update
helm install anvilops . -f values-dev.yaml
```

---

## Multi-Engineer Collaboration & State Locking

### How State Locking Works

AnvilOps uses **S3-native state locking** (`use_lockfile = true`, Terraform >= 1.11). When any engineer runs `terraform plan` or `terraform apply`:

1. Terraform creates a `.tflock` file in the S3 bucket using a conditional `PutObject` (`If-None-Match` header)
2. If the lock file already exists (another engineer is running), the write fails and Terraform displays:

   ```
   Error: Error acquiring the state lock
   Lock Info:
     ID:        xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
     Path:      anvilops-terraform-state-dev-.../platform/terraform.tfstate
     Operation: OperationTypeApply
     Who:       jane@macbook
     Created:   2026-03-01 12:34:56.789 +0000 UTC
   ```

3. When the operation finishes, Terraform deletes the lock file

### What This Means in Practice

| Scenario | What Happens |
|----------|--------------|
| Two engineers run `plan` simultaneously | Both succeed (plan is read-only, no lock needed for read) |
| Two engineers run `apply` simultaneously | Second one gets "Error acquiring the state lock" — waits and retries |
| Engineer's apply crashes mid-run | Lock file remains; must be manually removed (see below) |
| Engineer runs `apply` while another is planning | Apply acquires the lock; the plan does not block |

### Handling a Stale Lock

If an `apply` crashes or is killed (Ctrl+C, network drop), the lock file may remain:

```bash
# Force-unlock with the Lock ID from the error message
terraform force-unlock LOCK_ID
```

> **Warning**: Only use `force-unlock` when you are **certain** no other operation is running. Check with your team first.

### Best Practices for Teams

1. **Communicate before applying** — let your team know in Slack/chat before running `terraform apply` on shared infrastructure
2. **Use plan files** — always `terraform plan -out tfplan` then `terraform apply tfplan` to review before applying
3. **Don't run apply concurrently** — even with locking, coordinate who applies when
4. **Use separate workspaces** for independent work (e.g., per-server provisioning uses workspace isolation automatically)
5. **Keep tfvars local** — never commit `terraform.dev.tfvars` (contains IPs, zone IDs). Only commit the `.example` file
6. **Pin your IP** — each engineer sets their own `eks_public_access_cidrs` with their IP. Apply will merge the changes

### Managing Multiple Engineer IPs

When multiple engineers need EKS access, collect all IPs in the tfvars:

```hcl
eks_public_access_cidrs = [
  "104.55.73.102/32",   # Justin - home office
  "203.0.113.50/32",    # Jane - office
  "198.51.100.20/32",   # Bob - VPN
]
```

Each engineer updates the list with their IP and applies. Since state is locked, only one apply runs at a time.

---

## Quick Reference

| Action | Command |
|--------|---------|
| Find your public IP | `curl -s ifconfig.me` |
| Init Terraform | `terraform init -backend-config="bucket=anvilops-terraform-state-dev-ACCOUNT_ID" -backend-config="key=platform/terraform.tfstate" -backend-config="region=us-east-1" -backend-config="use_lockfile=true"` |
| Plan changes | `terraform plan -var-file terraform.dev.tfvars -out tfplan` |
| Apply changes | `terraform apply tfplan` |
| Connect kubectl | `aws eks update-kubeconfig --name anvilops-dev --region us-east-1` |
| Check cluster | `kubectl get nodes` |
| View state resources | `terraform state list` |
| Force-unlock stale lock | `terraform force-unlock LOCK_ID` |
