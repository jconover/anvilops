# =============================================================================
# AnvilOps Platform Infrastructure - Remote State Backend
# =============================================================================
# Uses S3 + DynamoDB for remote state with locking. Values are injected via
# partial backend configuration at init time to keep this config portable
# across environments.
#
# Initialize with:
#   terraform init \
#     -backend-config="bucket=anvilops-terraform-state-<environment>-<account_id>" \
#     -backend-config="key=platform/terraform.tfstate" \
#     -backend-config="region=us-east-1" \
#     -backend-config="dynamodb_table=anvilops-terraform-locks-<environment>" \
#     -backend-config="encrypt=true"
#
# The state-backend module creates the S3 bucket and DynamoDB table.
# Bootstrap: apply state-backend first with local backend, then migrate
# to S3 with `terraform init -migrate-state`.
# =============================================================================

terraform {
  backend "s3" {}
}
