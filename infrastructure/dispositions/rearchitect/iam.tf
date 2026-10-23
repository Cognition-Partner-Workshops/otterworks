locals {
  builder_policy_name = "${local.name}-builder"
}

data "aws_iam_policy_document" "builder" {
  statement {
    sid = "LambdaRunFunctions"
    actions = [
      "lambda:GetFunction",
      "lambda:GetFunctionConfiguration",
      "lambda:InvokeFunction",
      "lambda:UpdateFunctionCode",
      "lambda:UpdateFunctionConfiguration",
      "lambda:PublishVersion",
      "lambda:ListVersionsByFunction",
      "lambda:GetAlias",
      "lambda:ListAliases",
    ]
    resources = ["${local.arn_scope}:lambda:${data.aws_region.current.name}:${local.account}:function:${local.name}-*"]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/run_token"
      values   = [var.run_token]
    }
  }

  statement {
    sid       = "HttpApiOfRun"
    actions   = ["apigateway:GET", "apigateway:PATCH", "apigateway:POST", "apigateway:PUT"]
    resources = ["${local.arn_scope}:apigateway:${data.aws_region.current.name}::/apis/${aws_apigatewayv2_api.this.id}", "${local.arn_scope}:apigateway:${data.aws_region.current.name}::/apis/${aws_apigatewayv2_api.this.id}/*"]
  }

  statement {
    sid = "DataApiOnRunCluster"
    actions = [
      "rds-data:ExecuteStatement",
      "rds-data:BatchExecuteStatement",
      "rds-data:BeginTransaction",
      "rds-data:CommitTransaction",
      "rds-data:RollbackTransaction",
    ]
    resources = [aws_rds_cluster.this.arn]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/run_token"
      values   = [var.run_token]
    }
  }

  statement {
    sid       = "ReadRunDbSecret"
    actions   = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
    resources = [aws_secretsmanager_secret.db.arn]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/run_token"
      values   = [var.run_token]
    }
  }

  statement {
    sid = "ReadRunLogs"
    actions = [
      "logs:FilterLogEvents",
      "logs:GetLogEvents",
      "logs:DescribeLogStreams",
      "logs:StartQuery",
      "logs:StartLiveTail",
    ]
    resources = concat(
      [for group in aws_cloudwatch_log_group.lambda : "${group.arn}:*"],
      [for group in aws_cloudwatch_log_group.lambda : group.arn],
      [aws_cloudwatch_log_group.api.arn, "${aws_cloudwatch_log_group.api.arn}:*"],
    )
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/run_token"
      values   = [var.run_token]
    }
  }

  statement {
    sid = "CodeDeployRunApp"
    actions = [
      "codedeploy:CreateDeployment",
      "codedeploy:StopDeployment",
      "codedeploy:GetDeployment",
      "codedeploy:GetDeploymentGroup",
      "codedeploy:UpdateDeploymentGroup",
      "codedeploy:ListDeployments",
      "codedeploy:GetApplicationRevision",
      "codedeploy:RegisterApplicationRevision",
    ]
    resources = [
      aws_codedeploy_app.this.arn,
      "${local.arn_scope}:codedeploy:${data.aws_region.current.name}:${local.account}:deploymentgroup:${aws_codedeploy_app.this.name}/*",
    ]
  }

  statement {
    sid       = "CodeDeployConfigs"
    actions   = ["codedeploy:GetDeploymentConfig"]
    resources = ["${local.arn_scope}:codedeploy:${data.aws_region.current.name}:${local.account}:deploymentconfig:*"]
  }

  dynamic "statement" {
    for_each = local.probe_enabled ? [true] : []
    content {
      sid       = "RunProbe"
      actions   = ["synthetics:StartCanary", "synthetics:StopCanary"]
      resources = [aws_synthetics_canary.probe[0].arn]
    }
  }

  statement {
    sid       = "LogQueryResults"
    actions   = ["logs:GetQueryResults", "logs:StopQuery"]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "builder" {
  name        = local.builder_policy_name
  description = "${var.service_name} run ${local.name}: deploy and read run-scoped resources"
  policy      = data.aws_iam_policy_document.builder.json
  tags        = local.tags
}

resource "aws_iam_role_policy_attachment" "builder" {
  count      = var.builder_role_name == "" ? 0 : 1
  role       = var.builder_role_name
  policy_arn = aws_iam_policy.builder.arn
}
