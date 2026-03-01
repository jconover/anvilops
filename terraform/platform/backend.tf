# =============================================================================
# AnvilOps Platform Infrastructure - Remote State Backend
# =============================================================================
# Uses S3 with native locking (use_lockfile) for remote state. Values are
# injected via partial backend configuration at init time to keep this config
# portable across environments.
#
# Initialize with:
#   terraform init \
#     -backend-config="bucket=anvilops-terraform-state-<environment>-<account_id>" \
#     -backend-config="key=platform/terraform.tfstate" \
#     -backend-config="region=us-east-1" \
#     -backend-config="use_lockfile=true" \
#     -backend-config="encrypt=true"
#
# The state-backend module creates the S3 bucket (and a legacy DynamoDB table).
# Bootstrap: apply state-backend first with local backend, then migrate
# to S3 with `terraform init -migrate-state`.
# =============================================================================

terraform {
  backend "s3" {}
}
