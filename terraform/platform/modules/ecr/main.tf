locals {
  # Each AnvilOps container image gets its own ECR repository
  repositories = {
    api              = "${var.project_name}-api"
    worker           = "${var.project_name}-worker"
    frontend         = "${var.project_name}-frontend"
    terraform_runner = "${var.project_name}-terraform-runner"
  }

  # Lifecycle policy: keep last 30 tagged images, expire untagged after 7 days
  lifecycle_policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after 7 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 7
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Keep only the last 30 tagged images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["v", "sha-", "build-", "latest"]
          countType     = "imageCountMoreThan"
          countNumber   = 30
        }
        action = {
          type = "expire"
        }
      }
    ]
  })

  common_tags = merge(
    {
      Environment = var.environment
      ManagedBy   = "AnvilOps"
      Component   = "container-registry"
    },
    var.tags
  )
}

# ---------------------------------------------------------------------------
# ECR Repositories
# ---------------------------------------------------------------------------

resource "aws_ecr_repository" "this" {
  for_each = local.repositories

  name                 = each.value
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = merge(local.common_tags, {
    Name    = each.value
    Service = each.key
  })
}

# ---------------------------------------------------------------------------
# Lifecycle Policies -- applied to every repository
# ---------------------------------------------------------------------------

resource "aws_ecr_lifecycle_policy" "this" {
  for_each = local.repositories

  repository = aws_ecr_repository.this[each.key].name
  policy     = local.lifecycle_policy
}
