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
  permissions_boundary = aws_iam_policy.devin_engineer_boundary.arn
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

locals {
  engineer_boundary_name = "devin-aws-engineer-boundary"
  iam_arn                = "arn:${local.partition}:iam::${local.account_id}"
  aws_policy_arn         = "arn:${local.partition}:iam::aws:policy"

  # Policies the engineer may attach to a role it manages: customer policies of its own
  # runs, plus the AWS managed service policies the lp-* Terraform roots attach.
  engineer_attachable_policies = [
    "${local.iam_arn}:policy/lp-*",
    "${local.aws_policy_arn}/service-role/AWSCodeDeployRoleForLambdaLimited",
    "${local.aws_policy_arn}/AmazonSSMManagedInstanceCore",
    "${local.aws_policy_arn}/CloudWatchAgentServerPolicy",
  ]

  iam_read_actions = [
    "iam:Get*",
    "iam:List*",
    "iam:SimulatePrincipalPolicy",
    "iam:SimulateCustomPolicy",
  ]
}

# Permissions boundary of every role the engineer creates or edits, and of the builder
# role it attaches run policies to. A bounded role keeps the engineer's non-IAM reach at
# most and can write nothing in IAM, so no role the engineer touches outranks it.
resource "aws_iam_policy" "devin_engineer_boundary" {
  name        = local.engineer_boundary_name
  description = "Permissions boundary for roles managed by devin-aws-engineer"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "NonIamServices"
        Effect    = "Allow"
        NotAction = ["iam:*", "organizations:*", "account:*"]
        Resource  = "*"
      },
      {
        Sid      = "IamRead"
        Effect   = "Allow"
        Action   = local.iam_read_actions
        Resource = "*"
      },
      {
        Sid    = "NoDevinRoles"
        Effect = "Deny"
        Action = ["sts:AssumeRole", "sts:TagSession", "sts:SetSourceIdentity"]
        Resource = [
          "${local.iam_arn}:role/devin-*",
        ]
      },
    ]
  })
}

# PowerUserAccess leaves IAM out. The engineer role may create and wire the lp-* roles
# and policies that its own Terraform runs need. Every role it creates or edits must carry
# the devin-aws-engineer-boundary, it may attach only lp-* customer policies and a short
# list of AWS service policies, and it cannot write to the Devin roles, the boundary, the
# console user or the account's human users.
resource "aws_iam_role_policy" "devin_engineer_iam" {
  name = "devin-aws-engineer-iam"
  role = aws_iam_role.devin_engineer.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "IamRead"
        Effect   = "Allow"
        Action   = local.iam_read_actions
        Resource = "*"
      },
      {
        Sid    = "BoundedRunRoles"
        Effect = "Allow"
        Action = [ # nosemgrep: terraform.lang.security.iam.no-iam-priv-esc-funcs.no-iam-priv-esc-funcs, terraform.lang.security.iam.no-iam-resource-exposure.no-iam-resource-exposure
          "iam:CreateRole",
          "iam:DeleteRole",
          "iam:UpdateAssumeRolePolicy",
          "iam:PutRolePolicy",
          "iam:DeleteRolePolicy",
          "iam:PutRolePermissionsBoundary",
        ]
        Resource = ["${local.iam_arn}:role/lp-*"]
        Condition = {
          StringEquals = { "iam:PermissionsBoundary" = aws_iam_policy.devin_engineer_boundary.arn }
        }
      },
      {
        Sid      = "BoundedRunRoleAttachments"
        Effect   = "Allow"
        Action   = ["iam:AttachRolePolicy", "iam:DetachRolePolicy"] # nosemgrep: terraform.lang.security.iam.no-iam-priv-esc-funcs.no-iam-priv-esc-funcs, terraform.lang.security.iam.no-iam-resource-exposure.no-iam-resource-exposure
        Resource = ["${local.iam_arn}:role/lp-*"]
        Condition = {
          StringEquals = { "iam:PermissionsBoundary" = aws_iam_policy.devin_engineer_boundary.arn }
          ArnLike      = { "iam:PolicyARN" = local.engineer_attachable_policies }
        }
      },
      {
        Sid    = "RunRoleLifecycle"
        Effect = "Allow"
        Action = [ # nosemgrep: terraform.lang.security.iam.no-iam-priv-esc-funcs.no-iam-priv-esc-funcs, terraform.lang.security.iam.no-iam-resource-exposure.no-iam-resource-exposure
          "iam:UpdateRole",
          "iam:UpdateRoleDescription",
          "iam:TagRole",
          "iam:UntagRole",
          "iam:PassRole",
          "iam:CreateInstanceProfile",
          "iam:DeleteInstanceProfile",
          "iam:AddRoleToInstanceProfile",
          "iam:RemoveRoleFromInstanceProfile",
          "iam:TagInstanceProfile",
        ]
        Resource = [
          "${local.iam_arn}:role/lp-*",
          "${local.iam_arn}:instance-profile/lp-*",
        ]
      },
      {
        Sid      = "ServiceLinkedRoles"
        Effect   = "Allow"
        Action   = ["iam:CreateServiceLinkedRole"]
        Resource = ["${local.iam_arn}:role/aws-service-role/*"]
      },
      {
        Sid    = "RunPolicies"
        Effect = "Allow"
        Action = [ # nosemgrep: terraform.lang.security.iam.no-iam-priv-esc-funcs.no-iam-priv-esc-funcs, terraform.lang.security.iam.no-iam-resource-exposure.no-iam-resource-exposure
          "iam:CreatePolicy",
          "iam:DeletePolicy",
          "iam:CreatePolicyVersion",
          "iam:DeletePolicyVersion",
          "iam:SetDefaultPolicyVersion",
          "iam:TagPolicy",
          "iam:UntagPolicy",
        ]
        Resource = ["${local.iam_arn}:policy/lp-*"]
      },
      {
        Sid      = "RunPolicyOnBuilder"
        Effect   = "Allow"
        Action   = ["iam:AttachRolePolicy", "iam:DetachRolePolicy"] # nosemgrep: terraform.lang.security.iam.no-iam-priv-esc-funcs.no-iam-priv-esc-funcs, terraform.lang.security.iam.no-iam-resource-exposure.no-iam-resource-exposure
        Resource = [aws_iam_role.devin_builder.arn]
        Condition = {
          StringEquals = { "iam:PermissionsBoundary" = aws_iam_policy.devin_engineer_boundary.arn }
          ArnLike      = { "iam:PolicyARN" = "${local.iam_arn}:policy/lp-*" }
        }
      },
      {
        Sid    = "DenyUnboundedRoleWrites"
        Effect = "Deny"
        Action = [
          "iam:CreateRole",
          "iam:DeleteRole",
          "iam:UpdateAssumeRolePolicy",
          "iam:PutRolePolicy",
          "iam:DeleteRolePolicy",
          "iam:AttachRolePolicy",
          "iam:DetachRolePolicy",
          "iam:PutRolePermissionsBoundary",
        ]
        Resource = "*"
        Condition = {
          StringNotEquals = { "iam:PermissionsBoundary" = aws_iam_policy.devin_engineer_boundary.arn }
        }
      },
      {
        Sid       = "DenyOtherAttachablePolicies"
        Effect    = "Deny"
        Action    = ["iam:AttachRolePolicy", "iam:DetachRolePolicy"]
        Resource  = "*"
        Condition = { ArnNotLike = { "iam:PolicyARN" = local.engineer_attachable_policies } }
      },
      {
        Sid      = "DenyBoundaryRemoval"
        Effect   = "Deny"
        Action   = ["iam:DeleteRolePermissionsBoundary", "iam:DeleteUserPermissionsBoundary", "iam:PutUserPermissionsBoundary"]
        Resource = "*"
      },
      {
        Sid    = "DenyDevinRoleWrites"
        Effect = "Deny"
        NotAction = concat(local.iam_read_actions, [
          "iam:AttachRolePolicy",
          "iam:DetachRolePolicy",
        ])
        Resource = ["${local.iam_arn}:role/devin-*"]
      },
      {
        Sid       = "DenyUserGroupAndBoundaryWrites"
        Effect    = "Deny"
        NotAction = local.iam_read_actions
        Resource = [
          "${local.iam_arn}:user/*",
          "${local.iam_arn}:group/*",
          "${local.iam_arn}:policy/devin-*",
          aws_iam_policy.devin_engineer_boundary.arn,
        ]
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
