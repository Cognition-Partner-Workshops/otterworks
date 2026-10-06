terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # One state object per run token. scripts/lp-announcements.sh passes
  # -backend-config="key=otterworks/legacy-portal-announcements/<token>/terraform.tfstate".
  backend "s3" {
    bucket = "otterworks-terraform-state"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = local.tags
  }
}
