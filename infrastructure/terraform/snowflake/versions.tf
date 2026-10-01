terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 2.21"
    }
  }

  # Next to the tenant's demo-aws state (CONTRACTS.md §3.2):
  #   bucket = otterworks-terraform-state
  #   key    = otterworks/demo/<token>/snowflake.tfstate   (demo-aws: otterworks/demo/<token>/terraform.tfstate)
  # Supplied by ./tf.sh via -backend-config.
  backend "s3" {}
}

provider "aws" {
  region = var.region
  default_tags {
    tags = local.tags
  }
}

# The programmatic access token is never a Terraform variable: the provider reads it from SNOWFLAKE_TOKEN, which
# ./tf.sh exports from SNOWFLAKE_PAT for the terraform process only.
provider "snowflake" {
  organization_name = local.sf_organization
  account_name      = local.sf_account
  user              = var.snowflake_user != "" ? var.snowflake_user : null
  role              = var.snowflake_role
  warehouse         = var.snowflake_warehouse
  authenticator     = "PROGRAMMATIC_ACCESS_TOKEN"
}
