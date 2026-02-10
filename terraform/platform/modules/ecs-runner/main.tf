locals {
  cluster_name   = "${var.project_name}-terraform-${var.environment}"
  task_family    = "${var.project_name}-terraform-runner-${var.environment}"
  log_group_name = "/ecs/${var.project_name}-terraform-runner-${var.environment}"

  common_tags = merge(
    {
      Environment = var.environment
      ManagedBy   = "AnvilOps"
      Component   = "terraform-runner"
    },
    var.tags
  )
}

# ---------------------------------------------------------------------------
# ECS Cluster
# ---------------------------------------------------------------------------

resource "aws_ecs_cluster" "this" {
  name = local.cluster_name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = merge(local.common_tags, {
    Name = local.cluster_name
  })
}

resource "aws_ecs_cluster_capacity_providers" "this" {
  cluster_name = aws_ecs_cluster.this.name

  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE_SPOT"
    weight            = 1
  }
}

# ---------------------------------------------------------------------------
# CloudWatch Log Group
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "terraform_runner" {
  name              = local.log_group_name
  retention_in_days = 30

  tags = merge(local.common_tags, {
    Name = local.log_group_name
  })
}

# ---------------------------------------------------------------------------
# ECS Task Definition
# ---------------------------------------------------------------------------

resource "aws_ecs_task_definition" "terraform_runner" {
  family                   = local.task_family
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 1024
  memory                   = 2048
  execution_role_arn       = var.ecs_task_execution_role_arn
  task_role_arn            = var.ecs_terraform_runner_role_arn

  container_definitions = jsonencode([
    {
      name      = "terraform-runner"
      image     = var.terraform_runner_image
      essential = true

      environment = [
        {
          name  = "AWS_DEFAULT_REGION"
          value = var.aws_region
        },
        {
          name  = "TF_STATE_BUCKET"
          value = var.state_bucket_name
        },
        {
          name  = "TF_LOCK_TABLE"
          value = var.dynamodb_table_name
        }
      ]

      secrets = [
        {
          name      = "DATABASE_URL"
          valueFrom = var.db_secret_arn
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = local.log_group_name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "terraform"
        }
      }
    }
  ])

  tags = merge(local.common_tags, {
    Name = local.task_family
  })

  depends_on = [aws_cloudwatch_log_group.terraform_runner]
}
