locals {
  name = var.run_token

  tags = {
    demo      = "legacy-portal-ec2"
    run_token = var.run_token
    RunToken  = var.run_token
    Expires   = var.expires
    ManagedBy = "terraform"
  }

  jar_key         = "legacy-portal.jar"
  artifact_bucket = "${local.name}-artifacts"
  log_group_name  = "/otterworks/legacy-portal-ec2/${var.run_token}/app"
}

data "aws_partition" "current" {}

data "aws_vpc" "this" {
  tags = { Name = var.vpc_name }
}

data "aws_subnets" "public" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.this.id]
  }

  filter {
    name   = "tag:Name"
    values = ["${var.public_subnet_name_prefix}*"]
  }
}

# Amazon Linux 2023, x86_64. The instance runs in a public subnet because the
# otterworks-dev VPC has no NAT gateway; its security group still admits only
# the load balancer, so nothing off-VPC can reach it.
data "aws_ssm_parameter" "al2023_ami" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

# The jar is built by lp-ec2-up (./mvnw -q -DskipTests package in
# services/legacy-portal) before Terraform runs, so the object below reads a
# file that already exists.
resource "aws_s3_bucket" "artifacts" {
  bucket        = local.artifact_bucket
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_object" "jar" {
  bucket = aws_s3_bucket.artifacts.id
  key    = local.jar_key
  source = "${path.module}/${var.jar_path}"
  etag   = filemd5("${path.module}/${var.jar_path}")
}

resource "aws_cloudwatch_log_group" "app" {
  name              = local.log_group_name
  retention_in_days = var.log_retention_days
}

