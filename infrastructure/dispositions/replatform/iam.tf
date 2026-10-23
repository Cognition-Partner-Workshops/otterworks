locals {
  irsa_enabled = var.oidc_provider_arn != null
  oidc_issuer  = local.irsa_enabled ? element(split("oidc-provider/", var.oidc_provider_arn), 1) : ""
  role_name    = "${local.name}-${var.service_name}"
}

data "aws_iam_policy_document" "irsa_assume" {
  count = local.irsa_enabled ? 1 : 0

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_issuer}:sub"
      values   = ["system:serviceaccount:${var.namespace}:${local.service_account_name}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_issuer}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "service_account" {
  count                = local.irsa_enabled ? 1 : 0
  name                 = substr(local.role_name, 0, 64)
  description          = "IRSA role of ${var.service_name} (${var.namespace}/${local.service_account_name}) run ${local.name}"
  assume_role_policy   = data.aws_iam_policy_document.irsa_assume[0].json
  max_session_duration = 3600
  tags                 = local.tags
}

data "aws_iam_policy_document" "service_account" {
  count = local.irsa_enabled ? 1 : 0

  dynamic "statement" {
    for_each = length(aws_s3_bucket.this) > 0 ? [true] : []
    content {
      sid       = "ListBuckets"
      actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
      resources = [for bucket in aws_s3_bucket.this : bucket.arn]
    }
  }

  dynamic "statement" {
    for_each = length(aws_s3_bucket.this) > 0 ? [true] : []
    content {
      sid       = "ReadWriteObjects"
      actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
      resources = [for bucket in aws_s3_bucket.this : "${bucket.arn}/*"]
    }
  }

  dynamic "statement" {
    for_each = length(aws_sqs_queue.this) > 0 ? [true] : []
    content {
      sid = "UseQueues"
      actions = [
        "sqs:SendMessage",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:ChangeMessageVisibility",
        "sqs:GetQueueAttributes",
        "sqs:GetQueueUrl",
      ]
      resources = [for queue in aws_sqs_queue.this : queue.arn]
    }
  }

  dynamic "statement" {
    for_each = var.postgres == null ? [] : [true]
    content {
      sid       = "ReadDbSecret"
      actions   = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
      resources = [aws_secretsmanager_secret.postgres[0].arn]
    }
  }

  dynamic "statement" {
    for_each = var.iam_policy_statements
    content {
      sid       = statement.value.sid
      actions   = statement.value.actions
      resources = statement.value.resources
    }
  }
}

resource "aws_iam_role_policy" "service_account" {
  count  = local.irsa_enabled && (length(var.buckets) + length(var.queues) + length(var.iam_policy_statements) > 0 || var.postgres != null) ? 1 : 0
  name   = local.role_name
  role   = aws_iam_role.service_account[0].id
  policy = data.aws_iam_policy_document.service_account[0].json
}
