# =============================================================================
# AnvilOps Platform Infrastructure - Root Module
# =============================================================================
# Orchestrates all child modules to deploy the complete AnvilOps platform on
# AWS. Architecture:
#   Next.js + shadcn/ui -> FastAPI (EKS) -> Celery/Redis -> Terraform (ECS) -> AWS
#   Puppet Enterprise manages Day 2+ compliance on provisioned servers.
# =============================================================================

locals {
  name_prefix = "${var.project_name}-${var.environment}"

  common_tags = merge(
    {
      ProjectName = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
      Platform    = "AnvilOps"
    },
    var.tags
  )
}

# -----------------------------------------------------------------------------
# Networking - VPC, Subnets, NAT Gateways, Security Groups
# -----------------------------------------------------------------------------

module "networking" {
  source = "./modules/networking"

  project_name       = var.project_name
  environment        = var.environment
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
  single_nat_gateway = var.single_nat_gateway
  tags               = local.common_tags
}

# -----------------------------------------------------------------------------
# EKS Cluster - Runs API, AWX, Celery workers
# -----------------------------------------------------------------------------

module "eks" {
  source = "./modules/eks"

  project_name        = var.project_name
  environment         = var.environment
  private_subnet_ids  = module.networking.private_subnet_ids
  eks_security_group_id = module.networking.eks_security_group_id
  node_instance_types = var.eks_node_instance_types
  node_min_size       = var.eks_node_min_size
  node_max_size       = var.eks_node_max_size
  node_desired_size   = var.eks_node_desired_size
  tags                = local.common_tags
}

# -----------------------------------------------------------------------------
# RDS PostgreSQL - Primary datastore
# -----------------------------------------------------------------------------

module "rds" {
  source = "./modules/rds"

  project_name              = var.project_name
  environment               = var.environment
  isolated_subnet_ids       = module.networking.isolated_subnet_ids
  rds_security_group_id     = module.networking.rds_security_group_id
  db_instance_class         = var.db_instance_class
  db_allocated_storage      = var.db_allocated_storage
  db_name                   = var.db_name
  enable_deletion_protection = var.enable_deletion_protection
  tags                      = local.common_tags
}

# -----------------------------------------------------------------------------
# ElastiCache Redis - Celery message broker and result backend
# -----------------------------------------------------------------------------

module "elasticache" {
  source = "./modules/elasticache"

  project_name            = var.project_name
  environment             = var.environment
  isolated_subnet_ids     = module.networking.isolated_subnet_ids
  redis_security_group_id = module.networking.redis_security_group_id
  redis_node_type         = var.redis_node_type
  num_cache_clusters      = var.redis_num_cache_clusters
  sns_topic_arn           = module.monitoring.sns_topic_arn
  tags                    = local.common_tags
}

# -----------------------------------------------------------------------------
# ECR Repositories - Container images
# -----------------------------------------------------------------------------

module "ecr" {
  source = "./modules/ecr"

  project_name = var.project_name
  environment  = var.environment
  tags         = local.common_tags
}

# -----------------------------------------------------------------------------
# IAM - Roles, IRSA bindings, ECS task roles
# -----------------------------------------------------------------------------

module "iam" {
  source = "./modules/iam"

  project_name          = var.project_name
  environment           = var.environment
  eks_oidc_provider_arn = module.eks.oidc_provider_arn
  eks_oidc_provider_url = module.eks.oidc_provider_url
  state_bucket_arn      = module.state_backend.state_bucket_arn
  db_secret_arn         = module.rds.db_secret_arn
  redis_secret_arn      = module.elasticache.auth_token_secret_arn
  tags                  = local.common_tags
}

# -----------------------------------------------------------------------------
# ECS Runner - Ephemeral Fargate tasks for Terraform execution
# -----------------------------------------------------------------------------

module "ecs_runner" {
  source = "./modules/ecs-runner"

  project_name                  = var.project_name
  environment                   = var.environment
  aws_region                    = var.aws_region
  private_subnet_ids            = module.networking.private_subnet_ids
  ecs_runner_security_group_id  = module.networking.ecs_runner_security_group_id
  ecs_task_execution_role_arn   = module.iam.ecs_task_execution_role_arn
  ecs_terraform_runner_role_arn = module.iam.ecs_terraform_runner_role_arn
  terraform_runner_image        = "${module.ecr.terraform_runner_repository_url}:latest"
  state_bucket_name             = module.state_backend.state_bucket_name
  dynamodb_table_name           = module.state_backend.dynamodb_table_name
  db_secret_arn                 = module.rds.db_secret_arn
  tags                          = local.common_tags
}

# -----------------------------------------------------------------------------
# Cognito - User authentication and RBAC
# -----------------------------------------------------------------------------

module "cognito" {
  source = "./modules/cognito"

  project_name              = var.project_name
  environment               = var.environment
  callback_urls             = var.cognito_callback_urls
  logout_urls               = var.cognito_logout_urls
  enable_deletion_protection = var.enable_deletion_protection
  tags                      = local.common_tags
}

# -----------------------------------------------------------------------------
# ALB - Application Load Balancer, ACM, WAF
# -----------------------------------------------------------------------------

module "alb" {
  source = "./modules/alb"

  project_name              = var.project_name
  environment               = var.environment
  domain_name               = var.domain_name
  vpc_id                    = module.networking.vpc_id
  public_subnet_ids         = module.networking.public_subnet_ids
  alb_security_group_id     = module.networking.alb_security_group_id
  enable_waf                = var.enable_waf
  enable_deletion_protection = var.enable_deletion_protection
  tags                      = local.common_tags
}

# -----------------------------------------------------------------------------
# DNS - Route 53 hosted zone, records, health checks
# -----------------------------------------------------------------------------

module "dns" {
  source = "./modules/dns"

  project_name                    = var.project_name
  environment                     = var.environment
  domain_name                     = var.domain_name
  existing_zone_id                = var.existing_route53_zone_id
  alb_dns_name                    = module.alb.alb_dns_name
  alb_zone_id                     = module.alb.alb_zone_id
  cognito_domain_url              = module.cognito.user_pool_domain_url
  acm_domain_validation_options   = module.alb.acm_certificate_domain_validation_options
  sns_topic_arn                   = module.monitoring.sns_topic_arn
  tags                            = local.common_tags
}

# -----------------------------------------------------------------------------
# Monitoring - CloudWatch alarms, dashboard, SNS, log groups
# -----------------------------------------------------------------------------

module "monitoring" {
  source = "./modules/monitoring"

  project_name                      = var.project_name
  environment                       = var.environment
  alert_email                       = var.alert_email
  rds_instance_id                   = module.rds.db_instance_id
  elasticache_replication_group_id  = module.elasticache.replication_group_id
  alb_arn_suffix                    = module.alb.alb_arn_suffix
  ecs_cluster_name                  = module.ecs_runner.ecs_cluster_name
  eks_cluster_name                  = module.eks.cluster_name
  tags                              = local.common_tags
}

# -----------------------------------------------------------------------------
# Puppet Enterprise - Day 2+ compliance enforcement
# -----------------------------------------------------------------------------

module "puppet" {
  source = "./modules/puppet"

  project_name                 = var.project_name
  environment                  = var.environment
  puppet_ami_id                = var.puppet_ami_id
  puppet_instance_type         = var.puppet_instance_type
  private_subnet_ids           = module.networking.private_subnet_ids
  puppet_security_group_id     = module.networking.puppet_security_group_id
  puppet_instance_profile_name = module.iam.puppet_instance_profile_name
  domain_name                  = var.domain_name
  tags                         = local.common_tags
}

# -----------------------------------------------------------------------------
# State Backend - S3 + DynamoDB for server provisioning TF state
# -----------------------------------------------------------------------------

module "state_backend" {
  source = "./modules/state-backend"

  project_name = var.project_name
  environment  = var.environment
  tags         = local.common_tags
}
