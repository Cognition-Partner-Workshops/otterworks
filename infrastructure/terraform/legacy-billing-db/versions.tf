terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }

  # The state key is passed per run:
  # -backend-config="key=otterworks/legacy-billing-db/<run_token>/terraform.tfstate".
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
