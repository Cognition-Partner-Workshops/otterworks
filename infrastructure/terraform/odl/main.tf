terraform {
  required_version = ">= 1.7.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
  }
  backend "s3" {
    bucket = "otterworks-terraform-state"
    key    = "otterworks/odl/odl-1795112287/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = "us-east-1"
  default_tags {
    tags = {
      run_token = "odl-1795112287"
      Expires   = "2027-02-17T00:00:00Z"
      owner     = "otterworks-demo"
      demo      = "operational-data-layer"
    }
  }
}

resource "aws_ecr_repository" "images" {
  for_each     = toset(["mock-jira", "mock-pagerduty", "mock-confluence", "odl-seed", "oracle-free", "mongo", "odl-sync"])
  name         = "otterworks-odl/${each.key}"
  force_delete = true
  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "images" {
  for_each   = aws_ecr_repository.images
  repository = each.value.name
  policy = jsonencode({ rules = [{
    rulePriority = 1
    description  = "Keep last 10 images"
    selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 10 }
    action       = { type = "expire" }
  }] })
}

output "repository_urls" {
  value = { for name, repository in aws_ecr_repository.images : name => repository.repository_url }
}
