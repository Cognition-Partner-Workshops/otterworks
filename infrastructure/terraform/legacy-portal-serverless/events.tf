# Event-driven publish: the announcements function puts announcement.published on the run's bus
# after each create or publish; a rule hands each event to the consumer, which writes one item.
locals {
  bus_name           = "otterworks-${local.name}"
  notifications_name = "otterworks-${local.name}-notifications"
  consumer_name      = "${local.name}-notifications"
}

resource "aws_cloudwatch_event_bus" "this" {
  name = local.bus_name
}

resource "aws_dynamodb_table" "notifications" { # nosemgrep: terraform.aws.security.aws-dynamodb-table-unencrypted.aws-dynamodb-table-unencrypted
  name         = local.notifications_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "eventId"

  attribute {
    name = "eventId"
    type = "S"
  }

  server_side_encryption {
    enabled = true
  }
}

data "archive_file" "consumer" {
  type        = "zip"
  source_file = "${path.module}/consumer/handler.py"
  output_path = "${path.module}/.build/consumer.zip"
}

resource "aws_iam_role" "consumer" {
  name               = "${local.name}-consumer"
  description        = "Execution role of the ${local.name} notifications consumer"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "consumer" {
  statement {
    sid       = "WriteOwnLogs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.consumer.arn}:*"]
  }

  statement {
    sid       = "PutNotification"
    actions   = ["dynamodb:PutItem"]
    resources = [aws_dynamodb_table.notifications.arn]
  }
}

resource "aws_iam_role_policy" "consumer" {
  name   = "${local.name}-consumer"
  role   = aws_iam_role.consumer.id
  policy = data.aws_iam_policy_document.consumer.json
}

resource "aws_cloudwatch_log_group" "consumer" { # nosemgrep: terraform.aws.security.aws-cloudwatch-log-group-unencrypted.aws-cloudwatch-log-group-unencrypted
  name              = "/aws/lambda/${local.consumer_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "consumer" { # nosemgrep: terraform.aws.security.aws-lambda-x-ray-tracing-not-active.aws-lambda-x-ray-tracing-not-active
  function_name    = local.consumer_name
  description      = "Writes announcement.published events from ${local.bus_name} to ${local.notifications_name}"
  role             = aws_iam_role.consumer.arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.consumer.output_path
  source_code_hash = data.archive_file.consumer.output_base64sha256
  memory_size      = 128
  timeout          = 10

  environment { # nosemgrep: terraform.aws.security.aws-lambda-environment-unencrypted.aws-lambda-environment-unencrypted
    variables = {
      TABLE_NAME = aws_dynamodb_table.notifications.name
    }
  }

  depends_on = [aws_cloudwatch_log_group.consumer, aws_iam_role_policy.consumer]
}

resource "aws_cloudwatch_event_rule" "announcement_published" {
  name           = "${local.name}-announcement-published"
  description    = "announcement.published from the ${local.name} announcements function"
  event_bus_name = aws_cloudwatch_event_bus.this.name

  event_pattern = jsonencode({
    source      = ["otterworks.legacy-portal"]
    detail-type = ["announcement.published"]
  })
}

resource "aws_cloudwatch_event_target" "consumer" {
  rule           = aws_cloudwatch_event_rule.announcement_published.name
  event_bus_name = aws_cloudwatch_event_bus.this.name
  target_id      = "notifications-consumer"
  arn            = aws_lambda_function.consumer.arn

  retry_policy {
    maximum_retry_attempts       = 4
    maximum_event_age_in_seconds = 3600
  }
}

resource "aws_lambda_permission" "consumer" {
  statement_id  = "AllowAnnouncementPublishedRule"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.consumer.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.announcement_published.arn
}
