# Canary deployments. Each context function has a published version behind the alias "live", the
# HTTP API integrates with the alias, and CodeDeploy moves the alias. Terraform creates the alias on
# the first published version and then leaves its version and routing to CodeDeploy.
resource "aws_lambda_alias" "live" {
  for_each         = aws_lambda_function.context
  name             = "live"
  description      = "Traffic-serving version of ${each.value.function_name}, moved by CodeDeploy"
  function_name    = each.value.function_name
  function_version = each.value.version

  lifecycle {
    ignore_changes = [function_version, routing_config]
  }
}

resource "aws_iam_role" "codedeploy" {
  name        = "${local.name}-codedeploy"
  description = "CodeDeploy service role for the ${local.name} Lambda canaries"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "codedeploy.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = { StringEquals = { "aws:SourceAccount" = local.account } }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "codedeploy" {
  role       = aws_iam_role.codedeploy.name
  policy_arn = "${local.arn_scope}:iam::aws:policy/service-role/AWSCodeDeployRoleForLambdaLimited"
}

resource "aws_codedeploy_app" "this" {
  name             = local.name
  compute_platform = "Lambda"
}

resource "aws_codedeploy_deployment_group" "context" {
  for_each               = var.contexts
  app_name               = aws_codedeploy_app.this.name
  deployment_group_name  = each.key
  service_role_arn       = aws_iam_role.codedeploy.arn
  deployment_config_name = var.deployment_config_name

  deployment_style {
    deployment_option = "WITH_TRAFFIC_CONTROL"
    deployment_type   = "BLUE_GREEN"
  }

  auto_rollback_configuration {
    enabled = true
    events  = ["DEPLOYMENT_FAILURE", "DEPLOYMENT_STOP_ON_ALARM"]
  }

  alarm_configuration {
    enabled = true
    alarms  = [aws_cloudwatch_metric_alarm.api_5xx_rate.alarm_name, aws_cloudwatch_metric_alarm.lambda_errors.alarm_name]
  }

  depends_on = [aws_iam_role_policy_attachment.codedeploy]
}
