terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }

  # One state object per run token. scripts/lp-ec2.sh passes
  # -backend-config="key=otterworks/legacy-portal-ec2/<token>/terraform.tfstate".
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
