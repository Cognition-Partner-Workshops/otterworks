terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }

  # One state object per run token. scripts/lp-serverless.sh passes
  # -backend-config="key=otterworks/legacy-portal-serverless/<token>/terraform.tfstate".
  backend "s3" {
    bucket  = "otterworks-terraform-state"
    region  = "us-east-1"
    encrypt = true
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = local.tags
  }
}
