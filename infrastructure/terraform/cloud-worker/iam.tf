data "aws_iam_policy_document" "irsa_trust" {
  for_each = toset(["notification-service", "file-service"])

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.eks.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:sub"
      values   = ["system:serviceaccount:${var.tenant_namespace}:${each.key}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "notification_service" {
  name               = "otterworks-cw-notification-service"
  assume_role_policy = data.aws_iam_policy_document.irsa_trust["notification-service"].json
}

resource "aws_iam_role_policy" "notification_service" {
  name = "otterworks-cw-notification-service"
  role = aws_iam_role.notification_service.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility",
        ]
        Resource = [aws_sqs_queue.notifications.arn]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:Query",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Scan",
          "dynamodb:DescribeTable",
        ]
        Resource = [
          aws_dynamodb_table.notifications.arn,
          "${aws_dynamodb_table.notifications.arn}/index/*",
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
        ]
        Resource = [aws_dynamodb_table.notification_preferences.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["ses:SendEmail"]
        Resource = ["*"]
      },
    ]
  })
}

resource "aws_iam_role" "file_service" {
  name               = "otterworks-cw-file-service"
  assume_role_policy = data.aws_iam_policy_document.irsa_trust["file-service"].json
}

resource "aws_iam_role_policy" "file_service" {
  name = "otterworks-cw-file-service"
  role = aws_iam_role.file_service.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
        ]
        Resource = [
          "arn:${local.partition}:s3:::${local.file_bucket}",
          "arn:${local.partition}:s3:::${local.file_bucket}/*",
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
        ]
        Resource = flatten([for arn in local.file_table_arns : [arn, "${arn}/index/*"]])
      },
      {
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = [aws_sns_topic.events.arn]
      },
    ]
  })
}

resource "aws_iam_user" "devin_reader" {
  name = "devin-cw-reader"
}

data "aws_iam_policy_document" "devin_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = [aws_iam_user.devin_reader.arn]
    }
  }
}

resource "aws_iam_role" "devin_observer" {
  name                 = "devin-cw-observer"
  assume_role_policy   = data.aws_iam_policy_document.devin_trust.json
  max_session_duration = 14400
}

resource "aws_iam_role_policy_attachment" "devin_observer_read_only" {
  role       = aws_iam_role.devin_observer.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/ReadOnlyAccess"
}

resource "aws_iam_role" "devin_builder" {
  name                 = "devin-cw-builder"
  assume_role_policy   = data.aws_iam_policy_document.devin_trust.json
  max_session_duration = 14400
}

resource "aws_iam_role_policy_attachment" "devin_builder_read_only" {
  role       = aws_iam_role.devin_builder.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/ReadOnlyAccess"
}

resource "aws_iam_role_policy" "devin_builder" {
  name = "devin-cw-builder"
  role = aws_iam_role.devin_builder.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:StartMessageMoveTask",
          "sqs:ListMessageMoveTasks",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:PurgeQueue",
          "sqs:GetQueueAttributes",
        ]
        Resource = [
          aws_sqs_queue.notifications.arn,
          aws_sqs_queue.notifications_dlq.arn,
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = [aws_sqs_queue.notifications.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["cloudwatch:SetAlarmState"]
        Resource = [aws_cloudwatch_metric_alarm.dlq_depth.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = [aws_sns_topic.events.arn]
      },
    ]
  })
}

resource "aws_iam_role" "devin_engineer" {
  name                 = "devin-aws-engineer"
  assume_role_policy   = data.aws_iam_policy_document.devin_trust.json
  max_session_duration = 14400
}

resource "aws_iam_role_policy_attachment" "devin_engineer_power_user" {
  role       = aws_iam_role.devin_engineer.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/PowerUserAccess"
}

# PowerUserAccess leaves IAM out. The engineer role may create and wire the roles and
# policies that its own Terraform runs need, and nothing that touches the Devin roles,
# the console user or the account's human users.
resource "aws_iam_role_policy" "devin_engineer_iam" {
  name = "devin-aws-engineer-iam"
  role = aws_iam_role.devin_engineer.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "iam:Get*",
          "iam:List*",
          "iam:SimulatePrincipalPolicy",
          "iam:SimulateCustomPolicy",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "iam:CreateRole",
          "iam:DeleteRole",
          "iam:UpdateRole",
          "iam:UpdateRoleDescription",
          "iam:UpdateAssumeRolePolicy",
          "iam:TagRole",
          "iam:UntagRole",
          "iam:PutRolePolicy",
          "iam:DeleteRolePolicy",
          "iam:AttachRolePolicy",
          "iam:DetachRolePolicy",
          "iam:PassRole",
          "iam:CreateInstanceProfile",
          "iam:DeleteInstanceProfile",
          "iam:AddRoleToInstanceProfile",
          "iam:RemoveRoleFromInstanceProfile",
          "iam:TagInstanceProfile",
          "iam:CreateServiceLinkedRole",
        ]
        Resource = [
          "arn:${local.partition}:iam::${local.account_id}:role/lp-*",
          "arn:${local.partition}:iam::${local.account_id}:role/otterworks-*",
          "arn:${local.partition}:iam::${local.account_id}:role/aws-service-role/*",
          "arn:${local.partition}:iam::${local.account_id}:instance-profile/lp-*",
          "arn:${local.partition}:iam::${local.account_id}:instance-profile/otterworks-*",
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "iam:CreatePolicy",
          "iam:DeletePolicy",
          "iam:CreatePolicyVersion",
          "iam:DeletePolicyVersion",
          "iam:SetDefaultPolicyVersion",
          "iam:TagPolicy",
          "iam:UntagPolicy",
        ]
        Resource = [
          "arn:${local.partition}:iam::${local.account_id}:policy/lp-*",
          "arn:${local.partition}:iam::${local.account_id}:policy/otterworks-*",
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["iam:AttachRolePolicy", "iam:DetachRolePolicy"]
        Resource = [aws_iam_role.devin_builder.arn]
        Condition = {
          ArnLike = { "iam:PolicyARN" = "arn:${local.partition}:iam::${local.account_id}:policy/lp-*" }
        }
      },
    ]
  })
}

resource "aws_iam_user_policy" "devin_reader" {
  name = "devin-cw-reader-assume"
  user = aws_iam_user.devin_reader.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "sts:AssumeRole" # nosemgrep: terraform.lang.security.iam.no-iam-creds-exposure.no-iam-creds-exposure
      Resource = [
        aws_iam_role.devin_observer.arn,
        aws_iam_role.devin_builder.arn,
        aws_iam_role.devin_engineer.arn,
      ]
    }]
  })
}
