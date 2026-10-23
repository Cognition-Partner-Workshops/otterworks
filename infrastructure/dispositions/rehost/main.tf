locals {
  tags = merge(var.extra_tags, {
    run_token            = var.run_token
    RunToken             = var.run_token
    Expires              = var.expires
    ManagedBy            = "terraform"
    disposition          = "rehost"
    service              = var.service_name
    disposition_evidence = var.disposition_evidence
  })

  artifact_name   = coalesce(var.artifact_name, basename(var.artifact_path))
  artifact_bucket = "${var.run_token}-${substr(sha1(var.service_name), 0, 8)}-artifacts"
  log_group_name  = "/otterworks/dispositions/rehost/${var.run_token}/${var.service_name}"
  app_log_path    = coalesce(var.app_log_path, "/var/log/${var.service_name}/app.log")
  selected_ami    = var.ami_id != null ? var.ami_id : data.aws_ssm_parameter.al2023_ami[0].value
  listener_ports = merge(
    { http = 80 },
    var.certificate_arn == null ? {} : { https = 443 }
  )

  alb_ingress_rules = {
    for rule in flatten([
      for cidr in var.alb_ingress_cidrs : [
        for listener, port in local.listener_ports : {
          key      = "${listener}-${replace(cidr, "/", "-")}"
          cidr     = cidr
          listener = listener
          port     = port
        }
      ]
    ]) : rule.key => rule
  }

  environment_lines = join("\n", [
    for key, value in var.environment : "${key}=${jsonencode(value)}"
  ])
}

data "aws_partition" "current" {}

data "aws_region" "current" {}

data "aws_ssm_parameter" "al2023_ami" {
  count = var.ami_id == null ? 1 : 0
  name  = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_s3_bucket" "artifacts" {
  bucket        = local.artifact_bucket
  force_destroy = true
  tags          = merge(local.tags, { Name = local.artifact_bucket })
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_object" "artifact" {
  bucket = aws_s3_bucket.artifacts.id
  key    = local.artifact_name
  source = var.artifact_path
  etag   = filemd5(var.artifact_path)
  tags   = local.tags
}

resource "aws_cloudwatch_log_group" "app" { # nosemgrep: terraform.aws.security.aws-cloudwatch-log-group-unencrypted.aws-cloudwatch-log-group-unencrypted
  name              = local.log_group_name
  retention_in_days = var.log_retention_days
  tags              = local.tags
}
