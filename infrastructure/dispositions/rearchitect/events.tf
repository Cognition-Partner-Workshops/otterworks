resource "aws_cloudwatch_event_bus" "this" {
  name = local.bus_name
  tags = local.tags
}

data "archive_file" "consumer" {
  count       = length(var.event_subscriptions) > 0 ? 1 : 0
  type        = "zip"
  source_file = "${path.module}/consumer/handler.py"
  output_path = "${path.module}/.build/consumer.zip"
}

resource "aws_dynamodb_table" "subscription" { # nosemgrep: terraform.aws.security.aws-dynamodb-table-unencrypted.aws-dynamodb-table-unencrypted
  for_each     = var.event_subscriptions
  name         = "${local.name}-${each.key}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "eventId"
  tags         = local.tags

  attribute {
    name = "eventId"
    type = "S"
  }

  server_side_encryption {
    enabled = true
  }
}

resource "aws_iam_role" "consumer" {
  for_each           = var.event_subscriptions
  name               = "${local.name}-${each.key}-consumer"
  description        = "Execution role for the ${each.key} event consumer"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
  tags               = local.tags
}

data "aws_iam_policy_document" "consumer" {
  for_each = var.event_subscriptions

  statement {
    sid       = "WriteOwnLogs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.consumer[each.key].arn}:*"]
  }

  statement {
    sid       = "PutEvent"
    actions   = ["dynamodb:PutItem"]
    resources = [aws_dynamodb_table.subscription[each.key].arn]
  }
}

resource "aws_iam_role_policy" "consumer" {
  for_each = var.event_subscriptions
  name     = "${local.name}-${each.key}-consumer"
  role     = aws_iam_role.consumer[each.key].id
  policy   = data.aws_iam_policy_document.consumer[each.key].json
}

resource "aws_cloudwatch_log_group" "consumer" { # nosemgrep: terraform.aws.security.aws-cloudwatch-log-group-unencrypted.aws-cloudwatch-log-group-unencrypted
  for_each          = var.event_subscriptions
  name              = "/aws/lambda/${local.name}-${each.key}-consumer"
  retention_in_days = var.log_retention_days
  tags              = local.tags
}

resource "aws_lambda_function" "consumer" { # nosemgrep: terraform.aws.security.aws-lambda-x-ray-tracing-not-active.aws-lambda-x-ray-tracing-not-active
  for_each         = var.event_subscriptions
  function_name    = "${local.name}-${each.key}-consumer"
  description      = "Stores subscribed ${each.value.source} events"
  role             = aws_iam_role.consumer[each.key].arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.consumer[0].output_path
  source_code_hash = data.archive_file.consumer[0].output_base64sha256
  memory_size      = 128
  timeout          = 10
  tags             = local.tags

  environment { # nosemgrep: terraform.aws.security.aws-lambda-environment-unencrypted.aws-lambda-environment-unencrypted
    variables = {
      TABLE_NAME = aws_dynamodb_table.subscription[each.key].name
    }
  }

  depends_on = [aws_cloudwatch_log_group.consumer, aws_iam_role_policy.consumer]
}

resource "aws_cloudwatch_event_rule" "subscription" {
  for_each       = var.event_subscriptions
  name           = "${local.name}-${each.key}"
  description    = "Subscription to ${each.value.source} events"
  event_bus_name = aws_cloudwatch_event_bus.this.name
  event_pattern = jsonencode({
    source        = [each.value.source]
    "detail-type" = each.value.detail_types
  })
  tags = local.tags
}

resource "aws_cloudwatch_event_target" "consumer" {
  for_each       = var.event_subscriptions
  rule           = aws_cloudwatch_event_rule.subscription[each.key].name
  event_bus_name = aws_cloudwatch_event_bus.this.name
  target_id      = "${each.key}-consumer"
  arn            = aws_lambda_function.consumer[each.key].arn

  retry_policy {
    maximum_retry_attempts       = 4
    maximum_event_age_in_seconds = 3600
  }
}

resource "aws_lambda_permission" "consumer" {
  for_each      = var.event_subscriptions
  statement_id  = "AllowEventRule"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.consumer[each.key].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.subscription[each.key].arn
}
