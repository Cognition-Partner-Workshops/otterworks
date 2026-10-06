# Run-scoped grant for the Devin builder role. Lambda, the Data API, the DB secret and the log
# groups are matched by name prefix and by the run_token tag; the HTTP API is matched by its id,
# which is unique to the run. Everything the role can already read comes from ReadOnlyAccess.
data "aws_iam_role" "builder" {
  name = var.builder_role_name
}

locals {
  account   = data.aws_caller_identity.current.account_id
  arn_scope = "arn:${data.aws_partition.current.partition}"
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
    resources = ["${local.arn_scope}:lambda:${var.region}:${local.account}:function:${local.name}-*"]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/run_token"
      values   = [var.run_token]
    }
  }

  statement {
    sid       = "HttpApiOfRun"
    actions   = ["apigateway:GET", "apigateway:PATCH", "apigateway:POST", "apigateway:PUT"]
    resources = ["${local.arn_scope}:apigateway:${var.region}::/apis/${aws_apigatewayv2_api.this.id}", "${local.arn_scope}:apigateway:${var.region}::/apis/${aws_apigatewayv2_api.this.id}/*"]
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
    sid     = "ReadRunLogs"
    actions = ["logs:FilterLogEvents", "logs:GetLogEvents", "logs:DescribeLogStreams", "logs:StartQuery", "logs:StartLiveTail"]
    resources = concat(
      [for lg in aws_cloudwatch_log_group.lambda : "${lg.arn}:*"],
      [for lg in aws_cloudwatch_log_group.lambda : lg.arn],
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
      "${local.arn_scope}:codedeploy:${var.region}:${local.account}:deploymentgroup:${aws_codedeploy_app.this.name}/*",
    ]
  }

  statement {
    sid       = "CodeDeployConfigs"
    actions   = ["codedeploy:GetDeploymentConfig"]
    resources = ["${local.arn_scope}:codedeploy:${var.region}:${local.account}:deploymentconfig:*"]
  }

  statement {
    sid       = "RunProbe"
    actions   = ["synthetics:StartCanary", "synthetics:StopCanary"]
    resources = ["${local.arn_scope}:synthetics:${var.region}:${local.account}:canary:${local.probe_name}"]
  }

  statement {
    sid       = "LogQueryResults"
    actions   = ["logs:GetQueryResults", "logs:StopQuery"]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "builder" {
  name        = "${local.name}-builder"
  description = "legacy-portal-serverless run ${local.name}: deploy and read the run's functions, API, Data API, secret and logs"
  policy      = data.aws_iam_policy_document.builder.json
}

resource "aws_iam_role_policy_attachment" "builder" {
  role       = data.aws_iam_role.builder.name
  policy_arn = aws_iam_policy.builder.arn
}
