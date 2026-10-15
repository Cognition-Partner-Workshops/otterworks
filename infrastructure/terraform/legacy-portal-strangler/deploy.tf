# Canary deployments. The HTTP API invokes the alias "live"; Terraform creates it on the first published
# version and then leaves its version and routing to CodeDeploy, which shifts traffic to each newly
# published version and rolls back when either alarm in alarms.tf goes to ALARM.
resource "aws_iam_role" "codedeploy" {
  name        = "${local.name}-codedeploy"
  description = "CodeDeploy service role for the ${local.name} ${var.module} canary"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "codedeploy.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = { StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id } }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "codedeploy" {
  role       = aws_iam_role.codedeploy.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AWSCodeDeployRoleForLambdaLimited"
}

resource "aws_codedeploy_app" "this" {
  name             = local.name
  compute_platform = "Lambda"
}

resource "aws_codedeploy_deployment_group" "this" {
  app_name               = aws_codedeploy_app.this.name
  deployment_group_name  = var.module
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
