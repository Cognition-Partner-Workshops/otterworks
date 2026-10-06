# Synthetic probe: a Synthetics canary on a Node runtime calls GET announcements and GET preferences
# through the HTTP API every minute. It is created stopped; lp-deploy starts it once the Java handlers
# are live, so the placeholder's 501s never reach the 5xx alarm.
locals {
  probe_name = "${local.name}-probe"
}

resource "aws_s3_bucket" "probe_artifacts" { # nosemgrep: terraform.aws.security.aws-s3-bucket-versioning-not-enabled.aws-s3-bucket-versioning-not-enabled
  bucket        = "${local.name}-probe-artifacts-${local.account}"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "probe_artifacts" {
  bucket                  = aws_s3_bucket.probe_artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "probe_artifacts" {
  bucket = aws_s3_bucket.probe_artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "probe_artifacts" {
  bucket = aws_s3_bucket.probe_artifacts.id
  rule {
    id     = "expire-artifacts"
    status = "Enabled"
    filter {}
    expiration {
      days = 2
    }
  }
}

resource "aws_iam_role" "probe" {
  name               = "${local.name}-probe"
  description        = "Execution role of the ${local.probe_name} Synthetics canary"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "probe" {
  statement {
    sid       = "WriteArtifacts"
    actions   = ["s3:PutObject", "s3:GetObject"]
    resources = ["${aws_s3_bucket.probe_artifacts.arn}/*"]
  }

  statement {
    sid       = "LocateArtifactsBucket"
    actions   = ["s3:GetBucketLocation"]
    resources = [aws_s3_bucket.probe_artifacts.arn]
  }

  statement {
    sid       = "ListBuckets"
    actions   = ["s3:ListAllMyBuckets"]
    resources = ["*"]
  }

  statement {
    sid       = "WriteProbeLogs"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${local.arn_scope}:logs:${var.region}:${local.account}:log-group:/aws/lambda/cwsyn-${local.probe_name}-*"]
  }

  statement {
    sid       = "PutProbeMetrics"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["CloudWatchSynthetics"]
    }
  }
}

resource "aws_iam_role_policy" "probe" {
  name   = "${local.name}-probe"
  role   = aws_iam_role.probe.id
  policy = data.aws_iam_policy_document.probe.json
}

data "archive_file" "probe" {
  type        = "zip"
  source_dir  = "${path.module}/probe"
  output_path = "${path.module}/.build/probe.zip"
}

# The canary only picks up new code when its S3 key changes.
resource "aws_s3_object" "probe_code" {
  bucket = aws_s3_bucket.probe_artifacts.id
  key    = "code/probe-${data.archive_file.probe.output_md5}.zip"
  source = data.archive_file.probe.output_path
  etag   = data.archive_file.probe.output_md5
}

resource "aws_synthetics_canary" "probe" {
  name                 = local.probe_name
  artifact_s3_location = "s3://${aws_s3_bucket.probe_artifacts.bucket}/canary/"
  execution_role_arn   = aws_iam_role.probe.arn
  runtime_version      = var.probe_runtime_version
  handler              = "probe.handler"
  s3_bucket            = aws_s3_object.probe_code.bucket
  s3_key               = aws_s3_object.probe_code.key
  start_canary         = false
  delete_lambda        = true

  success_retention_period = 2
  failure_retention_period = 2

  schedule {
    expression = "rate(1 minute)"
  }

  run_config {
    timeout_in_seconds = 50
    environment_variables = {
      API_URL = aws_apigatewayv2_stage.default.invoke_url
    }
  }

  lifecycle {
    ignore_changes = [start_canary]
  }

  depends_on = [aws_iam_role_policy.probe]
}
