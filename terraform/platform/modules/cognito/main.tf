# =============================================================================
# AnvilOps Cognito Module
# =============================================================================
# User authentication with RBAC groups: Admin, Approver, Builder-Prod,
# Builder, Viewer. Includes resource server with custom API scopes.
# =============================================================================

locals {
  name_prefix = "${var.project_name}-${var.environment}"
  use_ses     = var.ses_email_identity_arn != ""

  rbac_groups = {
    "Admin" = {
      description = "Full platform access including user management and system configuration"
      precedence  = 0
    }
    "Approver" = {
      description = "Can approve or reject production server build requests"
      precedence  = 1
    }
    "Builder-Prod" = {
      description = "Can build servers in all environments including production"
      precedence  = 2
    }
    "Builder" = {
      description = "Can build servers in dev and staging environments only"
      precedence  = 3
    }
    "Viewer" = {
      description = "Read-only access to all resources and dashboards"
      precedence  = 4
    }
  }
}

data "aws_region" "current" {}

# -----------------------------------------------------------------------------
# KMS Customer Managed Key — Secrets Manager encryption
# -----------------------------------------------------------------------------

resource "aws_kms_key" "secrets" {
  description             = "CMK for AnvilOps Cognito Secrets Manager secrets"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  tags                    = var.tags
}

resource "aws_kms_alias" "secrets" {
  name          = "alias/${var.project_name}-${var.environment}-cognito-secrets"
  target_key_id = aws_kms_key.secrets.key_id
}

# -----------------------------------------------------------------------------
# CloudWatch Log Group — Cognito user activity logs
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "cognito_user_activity" {
  name              = "/aws/cognito/userpools/${local.name_prefix}/user-activity"
  retention_in_days = 365
  tags              = merge(var.tags, { Name = "${local.name_prefix}-cognito-user-activity" })
}

# -----------------------------------------------------------------------------
# User Pool
# -----------------------------------------------------------------------------

resource "aws_cognito_user_pool" "this" {
  name                     = local.name_prefix
  deletion_protection      = var.enable_deletion_protection ? "ACTIVE" : "INACTIVE"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  mfa_configuration        = var.mfa_configuration

  username_configuration {
    case_sensitive = false
  }

  software_token_mfa_configuration {
    enabled = true
  }

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 7
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  user_attribute_update_settings {
    attributes_require_verification_before_update = ["email"]
  }

  schema {
    name                     = "role"
    attribute_data_type      = "String"
    developer_only_attribute = false
    mutable                  = true
    required                 = false

    string_attribute_constraints {
      min_length = 1
      max_length = 64
    }
  }

  schema {
    name                     = "department"
    attribute_data_type      = "String"
    developer_only_attribute = false
    mutable                  = true
    required                 = false

    string_attribute_constraints {
      min_length = 1
      max_length = 128
    }
  }

  dynamic "email_configuration" {
    for_each = local.use_ses ? [1] : []
    content {
      email_sending_account  = "DEVELOPER"
      source_arn             = var.ses_email_identity_arn
      from_email_address     = var.ses_from_email
      reply_to_email_address = var.ses_from_email
    }
  }

  dynamic "email_configuration" {
    for_each = local.use_ses ? [] : [1]
    content {
      email_sending_account = "COGNITO_DEFAULT"
    }
  }

  admin_create_user_config {
    allow_admin_create_user_only = true

    invite_message_template {
      email_message = "Your AnvilOps account has been created. Username: {username}, Temporary password: {####}"
      email_subject = "Welcome to AnvilOps - Your Account Details"
      sms_message   = "Your AnvilOps username is {username} and temporary password is {####}"
    }
  }

  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
    email_message        = "Your AnvilOps verification code is: {####}"
    email_subject        = "AnvilOps - Email Verification Code"
  }

  user_pool_add_ons {
    advanced_security_mode = "ENFORCED"
  }

  tags = merge(var.tags, { Name = "${local.name_prefix}-cognito" })
}

# -----------------------------------------------------------------------------
# Cognito Event Logging — user activity to CloudWatch
# -----------------------------------------------------------------------------

resource "aws_cognito_user_pool_log_delivery_configuration" "this" {
  user_pool_id = aws_cognito_user_pool.this.id

  log_configurations {
    log_level    = "INFO"
    event_source = "userActivity"

    cloud_watch_logs_configuration {
      log_group_arn = "${aws_cloudwatch_log_group.cognito_user_activity.arn}:*"
    }
  }
}

# -----------------------------------------------------------------------------
# User Pool Domain (hosted UI)
# -----------------------------------------------------------------------------

resource "aws_cognito_user_pool_domain" "this" {
  domain       = local.name_prefix
  user_pool_id = aws_cognito_user_pool.this.id
}

# -----------------------------------------------------------------------------
# Resource Server (custom API scopes)
# -----------------------------------------------------------------------------

resource "aws_cognito_resource_server" "api" {
  identifier   = "anvilops-api"
  name         = "AnvilOps API"
  user_pool_id = aws_cognito_user_pool.this.id

  scope {
    scope_name        = "servers:read"
    scope_description = "Read access to server resources and build status"
  }

  scope {
    scope_name        = "servers:write"
    scope_description = "Create, update, and decommission servers"
  }

  scope {
    scope_name        = "servers:approve"
    scope_description = "Approve or reject production server build requests"
  }

  scope {
    scope_name        = "admin:manage"
    scope_description = "Full administrative access to platform configuration"
  }
}

# -----------------------------------------------------------------------------
# User Pool Client (web application)
# -----------------------------------------------------------------------------

resource "aws_cognito_user_pool_client" "web" {
  name         = "${local.name_prefix}-web"
  user_pool_id = aws_cognito_user_pool.this.id

  generate_secret = true

  allowed_oauth_flows                  = ["code"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes = concat(
    ["openid", "email", "profile"],
    [
      "${aws_cognito_resource_server.api.identifier}/servers:read",
      "${aws_cognito_resource_server.api.identifier}/servers:write",
      "${aws_cognito_resource_server.api.identifier}/servers:approve",
      "${aws_cognito_resource_server.api.identifier}/admin:manage",
    ]
  )

  callback_urls = var.callback_urls
  logout_urls   = var.logout_urls

  supported_identity_providers = ["COGNITO"]

  explicit_auth_flows = [
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_SRP_AUTH",
  ]

  access_token_validity  = 1
  id_token_validity      = 1
  refresh_token_validity = 7

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  prevent_user_existence_errors = "ENABLED"

  depends_on = [aws_cognito_resource_server.api]
}

# -----------------------------------------------------------------------------
# Client Secret in Secrets Manager
# -----------------------------------------------------------------------------

resource "aws_secretsmanager_secret" "client_secret" {
  name                    = "${local.name_prefix}/cognito/client-secret"
  description             = "Cognito client secret for ${local.name_prefix} web application"
  recovery_window_in_days = var.environment == "production" ? 30 : 7
  kms_key_id              = aws_kms_key.secrets.arn

  tags = merge(var.tags, { Name = "${local.name_prefix}-cognito-secret" })
}

resource "aws_secretsmanager_secret_version" "client_secret" {
  secret_id = aws_secretsmanager_secret.client_secret.id
  secret_string = jsonencode({
    user_pool_id    = aws_cognito_user_pool.this.id
    client_id       = aws_cognito_user_pool_client.web.id
    client_secret   = aws_cognito_user_pool_client.web.client_secret
    domain          = "https://${aws_cognito_user_pool_domain.this.domain}.auth.${data.aws_region.current.name}.amazoncognito.com"
    resource_server = aws_cognito_resource_server.api.identifier
  })
}

# -----------------------------------------------------------------------------
# RBAC Groups
# -----------------------------------------------------------------------------

resource "aws_cognito_user_group" "rbac" {
  for_each = local.rbac_groups

  name         = each.key
  user_pool_id = aws_cognito_user_pool.this.id
  description  = each.value.description
  precedence   = each.value.precedence
}
