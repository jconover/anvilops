# =============================================================================
# AnvilOps Secrets Manager Automatic Rotation Module
# =============================================================================
# This module enables automatic rotation for Secrets Manager secrets using
# AWS-managed Lambda rotation functions. No custom Lambda code is needed.
#
# How it works:
#   1. Secrets Manager invokes the AWS-provided rotation Lambda on the
#      configured schedule (default: every 30 days).
#   2. The Lambda connects to RDS, generates a new password, updates the
#      secret value, and then updates the RDS user password to match.
#   3. The RDS module's `ignore_changes = [password]` is intentional —
#      Secrets Manager owns the password lifecycle after initial creation.
#      Terraform will never overwrite a rotated password on subsequent plans.
#
# Usage (add to your environment's main.tf after the rds module call):
#
#   module "secrets_rotation" {
#     source = "../../modules/secrets-rotation"
#
#     project_name           = var.project_name
#     environment            = var.environment
#     secret_arn             = module.rds.db_secret_arn
#     rds_endpoint           = module.rds.db_endpoint
#     vpc_subnet_ids         = module.networking.private_subnet_ids
#     vpc_security_group_ids = [module.networking.rds_security_group_id]
#     rotation_days          = 30
#     tags                   = local.common_tags
#   }
# =============================================================================

locals {
  identifier = "${var.project_name}-${var.environment}"
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
data "aws_partition" "current" {}

# -----------------------------------------------------------------------------
# IAM Role for the Secrets Manager Rotation Lambda
# -----------------------------------------------------------------------------
# The AWS-managed rotation Lambda is provisioned into your VPC but its
# execution role must be created in your account so that it can call the
# Secrets Manager and RDS APIs.

resource "aws_iam_role" "rotation_lambda" {
  name        = "${local.identifier}-secrets-rotation-lambda"
  description = "Execution role for Secrets Manager RDS password rotation Lambda (${var.environment})"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowLambdaAssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      },
    ]
  })

  tags = merge(var.tags, { Name = "${local.identifier}-secrets-rotation-lambda" })
}

resource "aws_iam_role_policy_attachment" "rotation_lambda_vpc_access" {
  role       = aws_iam_role.rotation_lambda.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy" "rotation_lambda_secrets" {
  name = "${local.identifier}-secrets-rotation-policy"
  role = aws_iam_role.rotation_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowSecretsManagerAccess"
        Effect = "Allow"
        Action = [
          "secretsmanager:DescribeSecret",
          "secretsmanager:GetSecretValue",
          "secretsmanager:PutSecretValue",
          "secretsmanager:UpdateSecretVersionStage",
        ]
        Resource = var.secret_arn
      },
      {
        Sid    = "AllowSecretsManagerRandomPassword"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetRandomPassword",
        ]
        Resource = "*"
      },
      {
        Sid    = "AllowKMSForSecret"
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:DescribeKey",
        ]
        # Permit decryption of both the current secret version and the pending
        # version produced during rotation. Scoped to this account.
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:CallerAccount" = data.aws_caller_identity.current.account_id
          }
        }
      },
    ]
  })
}

# -----------------------------------------------------------------------------
# Security Group for the Rotation Lambda
# -----------------------------------------------------------------------------
# The Lambda needs egress to the RDS instance (port 5432) and to the
# Secrets Manager VPC endpoint (or NAT gateway) on port 443.

resource "aws_security_group" "rotation_lambda" {
  name        = "${local.identifier}-secrets-rotation-lambda"
  description = "Security group for Secrets Manager RDS rotation Lambda (${var.environment})"
  vpc_id      = var.vpc_id

  egress {
    description     = "Allow Lambda to reach RDS on PostgreSQL port"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = var.vpc_security_group_ids
  }

  egress {
    description = "Allow Lambda to reach Secrets Manager API (VPC endpoint or NAT)"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, { Name = "${local.identifier}-secrets-rotation-lambda" })

  lifecycle {
    create_before_destroy = true
  }
}

# -----------------------------------------------------------------------------
# AWS-Managed Rotation Lambda (SecretsManagerRDSPostgreSQLRotationSingleUser)
# -----------------------------------------------------------------------------
# AWS publishes pre-built rotation Lambda packages in every region via the
# Serverless Application Repository. The SAR app name for single-user
# PostgreSQL rotation is "SecretsManagerRDSPostgreSQLRotationSingleUser".
# Deploying the SAR app provisions the Lambda function with all required
# handler code — no ZIP upload is needed.

resource "aws_serverlessapplicationrepository_cloudformation_stack" "rotation_lambda" {
  name           = "${local.identifier}-rds-rotation-lambda"
  application_id = "arn:${data.aws_partition.current.partition}:serverlessrepo:us-east-1:912272126622:applications/SecretsManagerRDSPostgreSQLRotationSingleUser"

  # Always use the latest published semantic version. Pin this to a specific
  # version string (e.g. "1.1.367") in production if change control requires it.
  semantic_version = var.rotation_lambda_version

  capabilities = [
    "CAPABILITY_IAM",
    "CAPABILITY_RESOURCE_POLICY",
  ]

  parameters = {
    endpoint            = "https://secretsmanager.${data.aws_region.current.region}.amazonaws.com"
    functionName        = "${local.identifier}-rds-rotation"
    vpcSubnetIds        = join(",", var.vpc_subnet_ids)
    vpcSecurityGroupIds = aws_security_group.rotation_lambda.id
  }

  tags = merge(var.tags, { Name = "${local.identifier}-rds-rotation-lambda" })
}

locals {
  # The SAR stack outputs the Lambda ARN under the key "RotationLambdaARN".
  rotation_lambda_arn = aws_serverlessapplicationrepository_cloudformation_stack.rotation_lambda.outputs["RotationLambdaARN"]
}

# -----------------------------------------------------------------------------
# Secrets Manager Rotation Configuration
# -----------------------------------------------------------------------------

resource "aws_secretsmanager_secret_rotation" "rds" {
  secret_id           = var.secret_arn
  rotation_lambda_arn = local.rotation_lambda_arn

  rotation_rules {
    automatically_after_days = var.rotation_days
  }

  depends_on = [
    aws_serverlessapplicationrepository_cloudformation_stack.rotation_lambda,
    aws_iam_role_policy_attachment.rotation_lambda_vpc_access,
    aws_iam_role_policy.rotation_lambda_secrets,
  ]
}
