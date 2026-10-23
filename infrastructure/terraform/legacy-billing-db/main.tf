locals {
  name = "${var.run_token}-legacy-billing"
  port = 5432

  tags = {
    demo      = "legacy-billing-db"
    Service   = "legacy-billing"
    run_token = var.run_token
    RunToken  = var.run_token
    Expires   = var.expires
    ManagedBy = "terraform"
  }

  log_exports = ["postgresql", "upgrade"]
}

data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

data "aws_region" "current" {}

data "aws_vpc" "this" {
  tags = { Name = var.vpc_name }
}

data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.this.id]
  }

  filter {
    name   = "tag:Name"
    values = ["${var.private_subnet_name_prefix}*"]
  }
}
