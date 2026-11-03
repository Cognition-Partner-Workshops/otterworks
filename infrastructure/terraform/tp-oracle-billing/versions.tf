terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }

  backend "s3" {
    bucket = "otterworks-terraform-state"
    key    = "otterworks/tp-oracle-billing/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = "otterworks-tp"
      Component = "legacy-oracle-billing"
      ManagedBy = "terraform"
    }
  }
}
