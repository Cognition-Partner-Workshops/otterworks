terraform {
  required_version = ">= 1.7.0"

  backend "s3" {
    bucket = "otterworks-terraform-state"
    region = "us-east-1"
    # Pass -backend-config="key=otterworks/dispositions/rehost/<run_token>/terraform.tfstate".
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }
}

provider "aws" {
  region = var.region
}
