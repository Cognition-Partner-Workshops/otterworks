data "archive_file" "placeholder" {
  type        = "zip"
  source_file = "${path.module}/placeholder/handler.py"
  output_path = "${path.module}/.build/placeholder.zip"
}

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
  description        = "Execution role of the ${local.name} context functions"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "lambda" {
  statement {
    sid       = "WriteOwnLogs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = [for lg in aws_cloudwatch_log_group.lambda : "${lg.arn}:*"]
  }

  statement {
    sid = "DataApi"
    actions = [
      "rds-data:ExecuteStatement",
      "rds-data:BatchExecuteStatement",
      "rds-data:BeginTransaction",
      "rds-data:CommitTransaction",
      "rds-data:RollbackTransaction",
    ]
    resources = [aws_rds_cluster.this.arn]
  }

  statement {
    sid       = "ReadDbSecret"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_rds_cluster.this.master_user_secret[0].secret_arn]
  }

  statement {
    sid       = "PutAnnouncementEvents"
    actions   = ["events:PutEvents"]
    resources = [aws_cloudwatch_event_bus.this.arn]
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = "${local.name}-lambda"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda.json
}

resource "aws_cloudwatch_log_group" "lambda" { # nosemgrep: terraform.aws.security.aws-cloudwatch-log-group-unencrypted.aws-cloudwatch-log-group-unencrypted
  for_each          = local.function_names
  name              = "/aws/lambda/${each.value}"
  retention_in_days = var.log_retention_days
}

# Placeholder handlers answer 501. The real handlers are deployed with update-function-code (by a child
# session or lp-deploy), so Terraform leaves code and runtime alone after create. publish creates the
# version the live alias starts on.
resource "aws_lambda_function" "context" { # nosemgrep: terraform.aws.security.aws-lambda-x-ray-tracing-not-active.aws-lambda-x-ray-tracing-not-active
  for_each         = var.contexts
  function_name    = local.function_names[each.key]
  description      = "legacy-portal ${each.key} context (${local.name})"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.placeholder.output_path
  source_code_hash = data.archive_file.placeholder.output_base64sha256
  memory_size      = var.lambda_memory_mb
  timeout          = 29
  architectures    = ["x86_64"]
  publish          = true

  environment { # nosemgrep: terraform.aws.security.aws-lambda-environment-unencrypted.aws-lambda-environment-unencrypted
    variables = merge({
      CONTEXT     = each.key
      DB_SCHEMA   = each.value.schema
      DB_NAME     = aws_rds_cluster.this.database_name
      CLUSTER_ARN = aws_rds_cluster.this.arn
      SECRET_ARN  = aws_rds_cluster.this.master_user_secret[0].secret_arn
      RUN_TOKEN   = var.run_token
      FAIL_READS  = "0"
    }, each.key == "announcements" ? { EVENT_BUS_NAME = aws_cloudwatch_event_bus.this.name } : {})
  }

  lifecycle {
    ignore_changes = [filename, source_code_hash, runtime, handler, memory_size, layers, snap_start]
  }

  depends_on = [aws_cloudwatch_log_group.lambda, aws_iam_role_policy.lambda]
}
