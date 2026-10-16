# ------------------------------------------------------------------------------
# OtterWorks Platform - ECR Module
# Container registries for all microservices
# ------------------------------------------------------------------------------

locals {
  common_tags = {
    Module  = "ecr"
    Project = var.project
  }
}

resource "aws_ecr_repository" "services" {
  for_each = toset(var.service_names)

  name                 = "${var.ecr_prefix}${each.value}"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = var.environment == "dev"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(local.common_tags, {
    Service = each.value
  })
}

resource "aws_ecr_lifecycle_policy" "services" {
  for_each = aws_ecr_repository.services

  repository = each.value.name

  policy = jsonencode({
    # An image matched by a rule can't be expired by a lower-priority one, so
    # the golden `main` builds and the images tenants point at survive a branch
    # that pushes a dozen builds in an afternoon. With only the catch-all rule,
    # that churn expired `:main` and t-main fell back to a branch image.
    rules = [
      {
        rulePriority = 1
        description  = "Keep the last 5 golden (main) builds"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["main"]
          countType     = "imageCountMoreThan"
          countNumber   = 5
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Keep the last 30 images a tenant points at"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["tenant-"]
          countType     = "imageCountMoreThan"
          countNumber   = 30
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 3
        description  = "Keep last 10 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
