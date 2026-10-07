# Nightly usage export to S3 (decision d-export-network = relay). The private
# subnets have no NAT and no VPC endpoints, so an in-VPC function cannot reach
# S3 or Secrets Manager. The export function therefore runs outside the VPC:
# it reads the run's login secret, invokes the in-VPC sql-runner (db_sql) with
# the credential in the payload, and writes s3://<bucket>/usage/period=<yyyy-mm>/.
# Nothing is added to the shared VPC or the shared instance.

data "aws_caller_identity" "current" {}

locals {
  usage_bucket       = "${local.name}-billing-usage-${data.aws_caller_identity.current.account_id}"
  usage_export       = "${local.name}-billing-usage-export"
  usage_export_role  = "otterworks-${local.name}-usage-export"
  usage_sched_role   = "otterworks-${local.name}-usage-scheduler"
  usage_export_build = "${path.module}/.build/usage_export"
}

resource "aws_s3_bucket" "usage" {
  bucket        = local.usage_bucket
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "usage" {
  bucket                  = aws_s3_bucket.usage.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "usage" {
  bucket = aws_s3_bucket.usage.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "usage" {
  bucket = aws_s3_bucket.usage.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

data "aws_iam_policy_document" "usage_bucket" {
  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.usage.arn, "${aws_s3_bucket.usage.arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "usage" {
  bucket     = aws_s3_bucket.usage.id
  policy     = data.aws_iam_policy_document.usage_bucket.json
  depends_on = [aws_s3_bucket_public_access_block.usage]
}

# Export function: outside the VPC, so it reaches Secrets Manager, Lambda and S3
# on their public endpoints.

resource "aws_iam_role" "usage_export" {
  name               = local.usage_export_role
  description        = "Execution role of ${local.usage_export}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "usage_export" {
  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.usage_export.arn}:*"]
  }
  statement {
    sid       = "ReadRunSecret"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.billing_db.arn]
  }
  statement {
    sid       = "InvokeSqlRunner"
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.db_sql.arn]
  }
  statement {
    sid       = "ListExportPrefixes"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.usage.arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["usage/*", "manifests/usage/*"]
    }
  }
  statement {
    sid       = "WriteExportObjects"
    actions   = ["s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.usage.arn}/usage/*", "${aws_s3_bucket.usage.arn}/manifests/usage/*"]
  }
}

resource "aws_iam_role_policy" "usage_export" {
  name   = local.usage_export_role
  role   = aws_iam_role.usage_export.id
  policy = data.aws_iam_policy_document.usage_export.json
}

resource "aws_cloudwatch_log_group" "usage_export" { # nosemgrep: terraform.aws.security.aws-cloudwatch-log-group-unencrypted.aws-cloudwatch-log-group-unencrypted
  name              = "/aws/lambda/${local.usage_export}"
  retention_in_days = var.log_retention_days
}

# build-lambda.sh copies usage_export/handler.py into .build/usage_export (boto3 comes with the runtime).
data "archive_file" "usage_export" {
  type        = "zip"
  source_dir  = local.usage_export_build
  output_path = "${path.module}/.build/usage_export.zip"
}

resource "aws_lambda_function" "usage_export" { # nosemgrep: terraform.aws.security.aws-lambda-x-ray-tracing-not-active.aws-lambda-x-ray-tracing-not-active
  function_name    = local.usage_export
  description      = "Exports billing.usage_events of ${local.db_name} to s3://${local.usage_bucket}/usage/ via ${local.db_sql}"
  role             = aws_iam_role.usage_export.arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.usage_export.output_path
  source_code_hash = data.archive_file.usage_export.output_base64sha256
  memory_size      = 256
  timeout          = 300
  architectures    = ["x86_64"]

  environment { # nosemgrep: terraform.aws.security.aws-lambda-environment-unencrypted.aws-lambda-environment-unencrypted
    variables = {
      USAGE_BUCKET = aws_s3_bucket.usage.id
      DB_SECRET_ID = aws_secretsmanager_secret.billing_db.arn
      SQL_FUNCTION = aws_lambda_function.db_sql.function_name
    }
  }

  depends_on = [aws_cloudwatch_log_group.usage_export, aws_iam_role_policy.usage_export]
}

# Nightly schedule. Schedules themselves take no tags, so they live in a
# schedule group of their own that carries run_token and Expires.

resource "aws_scheduler_schedule_group" "usage" {
  name = "${local.name}-billing"
}

data "aws_iam_policy_document" "scheduler_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "usage_scheduler" {
  name               = local.usage_sched_role
  description        = "EventBridge Scheduler role that invokes ${local.usage_export}"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

data "aws_iam_policy_document" "usage_scheduler" {
  statement {
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.usage_export.arn]
  }
}

resource "aws_iam_role_policy" "usage_scheduler" {
  name   = local.usage_sched_role
  role   = aws_iam_role.usage_scheduler.id
  policy = data.aws_iam_policy_document.usage_scheduler.json
}

resource "aws_scheduler_schedule" "usage_export" {
  name        = "${local.name}-billing-usage-export"
  group_name  = aws_scheduler_schedule_group.usage.name
  description = "Nightly export of billing usage (${local.db_name}) to s3://${local.usage_bucket}/usage/"

  schedule_expression          = var.usage_export_schedule
  schedule_expression_timezone = "UTC"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.usage_export.arn
    role_arn = aws_iam_role.usage_scheduler.arn
    input    = jsonencode({})

    retry_policy {
      maximum_retry_attempts       = 2
      maximum_event_age_in_seconds = 3600
    }
  }

  depends_on = [aws_iam_role_policy.usage_scheduler]
}
