data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${local.name}-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "lambda" {
  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.lambda.arn}:*"]
  }

  statement {
    sid       = "DataApi"
    actions   = ["rds-data:ExecuteStatement", "rds-data:BatchExecuteStatement"]
    resources = [aws_rds_cluster.this.arn]
  }

  statement {
    sid       = "DbSecret"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.db.arn]
  }

  dynamic "statement" {
    for_each = local.events ? [aws_cloudwatch_event_bus.this[0].arn] : []
    content {
      sid       = "PublishAnnouncementEvents"
      actions   = ["events:PutEvents"]
      resources = [statement.value]
    }
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = var.module
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda.json
}

resource "aws_cloudwatch_log_group" "lambda" { # nosemgrep: terraform.aws.security.aws-cloudwatch-log-group-unencrypted.aws-cloudwatch-log-group-unencrypted
  name              = "/aws/lambda/${local.name}-${var.module}"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "this" { # nosemgrep: terraform.aws.security.aws-lambda-x-ray-tracing-not-active.aws-lambda-x-ray-tracing-not-active
  function_name    = "${local.name}-${var.module}"
  description      = "legacy-portal ${var.module} context (${local.name}); other routes stay on ${var.ec2_run_token}"
  role             = aws_iam_role.lambda.arn
  runtime          = "java21"
  handler          = local.m.handler
  filename         = var.jar_path
  source_code_hash = filebase64sha256(var.jar_path)
  memory_size      = var.lambda_memory_mb
  timeout          = 29
  architectures    = ["x86_64"]
  publish          = true

  snap_start {
    apply_on = "PublishedVersions"
  }

  environment { # nosemgrep: terraform.aws.security.aws-lambda-environment-unencrypted.aws-lambda-environment-unencrypted
    variables = merge({
      DB_SCHEMA   = local.m.schema
      DB_NAME     = aws_rds_cluster.this.database_name
      CLUSTER_ARN = aws_rds_cluster.this.arn
      SECRET_ARN  = aws_secretsmanager_secret.db.arn
      RUN_TOKEN   = var.run_token
      FAIL_READS  = "0"
    }, local.events ? { EVENT_BUS_NAME = aws_cloudwatch_event_bus.this[0].name } : {})
  }

  depends_on = [aws_cloudwatch_log_group.lambda, aws_iam_role_policy.lambda, terraform_data.schema]
}

# SnapStart applies to published versions only, so the API invokes this alias, never $LATEST.
resource "aws_lambda_alias" "live" {
  name             = "live"
  function_name    = aws_lambda_function.this.function_name
  function_version = aws_lambda_function.this.version
}
