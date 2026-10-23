data "archive_file" "probe" {
  count       = local.probe_enabled ? 1 : 0
  type        = "zip"
  source_dir  = "${path.module}/probe"
  output_path = "${path.module}/.build/probe.zip"
}

resource "aws_s3_bucket" "probe_artifacts" { # nosemgrep: terraform.aws.security.aws-s3-bucket-versioning-not-enabled.aws-s3-bucket-versioning-not-enabled
  count         = local.probe_enabled ? 1 : 0
  bucket_prefix = "${local.name}-probe-"
  force_destroy = true
  tags          = local.tags
}

resource "aws_s3_bucket_public_access_block" "probe_artifacts" {
  count                   = local.probe_enabled ? 1 : 0
  bucket                  = aws_s3_bucket.probe_artifacts[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "probe_artifacts" {
  count  = local.probe_enabled ? 1 : 0
  bucket = aws_s3_bucket.probe_artifacts[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "probe_artifacts" {
  count  = local.probe_enabled ? 1 : 0
  bucket = aws_s3_bucket.probe_artifacts[0].id

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
  count              = local.probe_enabled ? 1 : 0
  name               = local.probe_name
  description        = "Execution role of the ${local.probe_name} Synthetics canary"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
  tags               = local.tags
}

data "aws_iam_policy_document" "probe" {
  count = local.probe_enabled ? 1 : 0

  statement {
    sid       = "WriteArtifacts"
    actions   = ["s3:PutObject", "s3:GetObject"]
    resources = ["${aws_s3_bucket.probe_artifacts[0].arn}/*"]
  }

  statement {
    sid       = "LocateArtifactsBucket"
    actions   = ["s3:GetBucketLocation"]
    resources = [aws_s3_bucket.probe_artifacts[0].arn]
  }

  statement {
    sid       = "ListBuckets"
    actions   = ["s3:ListAllMyBuckets"]
    resources = ["*"]
  }

  statement {
    sid       = "WriteProbeLogs"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${local.arn_scope}:logs:${data.aws_region.current.name}:${local.account}:log-group:/aws/lambda/cwsyn-${local.probe_name}-*"]
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
  count  = local.probe_enabled ? 1 : 0
  name   = local.probe_name
  role   = aws_iam_role.probe[0].id
  policy = data.aws_iam_policy_document.probe[0].json
}

resource "aws_s3_object" "probe_code" {
  count  = local.probe_enabled ? 1 : 0
  bucket = aws_s3_bucket.probe_artifacts[0].id
  key    = "code/probe-${data.archive_file.probe[0].output_md5}.zip"
  source = data.archive_file.probe[0].output_path
  etag   = data.archive_file.probe[0].output_md5
  tags   = local.tags
}

resource "aws_synthetics_canary" "probe" {
  count                    = local.probe_enabled ? 1 : 0
  name                     = local.probe_name
  artifact_s3_location     = "s3://${aws_s3_bucket.probe_artifacts[0].bucket}/canary/"
  execution_role_arn       = aws_iam_role.probe[0].arn
  runtime_version          = var.probe_runtime_version
  handler                  = "probe.handler"
  s3_bucket                = aws_s3_object.probe_code[0].bucket
  s3_key                   = aws_s3_object.probe_code[0].key
  start_canary             = false
  delete_lambda            = true
  success_retention_period = 2
  failure_retention_period = 2
  tags                     = local.tags

  schedule {
    expression = "rate(1 minute)"
  }

  run_config {
    timeout_in_seconds = 50
    environment_variables = {
      API_URL     = aws_apigatewayv2_stage.default.invoke_url
      PROBE_STEPS = jsonencode(var.probe_steps)
    }
  }

  lifecycle {
    ignore_changes = [start_canary]
  }

  depends_on = [aws_iam_role_policy.probe]
}
