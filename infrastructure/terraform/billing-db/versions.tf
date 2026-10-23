terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }

  # One state object per run token, passed at init:
  # -backend-config="key=otterworks/billing-db/<token>/terraform.tfstate".
  # PR CI runs `terraform init -backend=false` and never touches this bucket.
  backend "s3" {
    bucket = "otterworks-terraform-state"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.region

  # PR jobs get no AWS credentials. With offline_plan = true (ci/offline.tfvars)
  # the provider never calls STS, so a plan runs on mock credentials.
  skip_credentials_validation = var.offline_plan
  skip_requesting_account_id  = var.offline_plan
  skip_metadata_api_check     = var.offline_plan

  default_tags {
    tags = local.tags
  }
}
