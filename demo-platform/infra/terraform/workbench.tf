resource "aws_dynamodb_table" "workbench_attendee_state" { # nosemgrep: terraform.aws.security.aws-dynamodb-table-unencrypted.aws-dynamodb-table-unencrypted -- server-side encryption uses the AWS-owned key per design
  name         = "workbench-attendee-state"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user"
  range_key    = "doc"

  attribute {
    name = "user"
    type = "S"
  }

  attribute {
    name = "doc"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  server_side_encryption {
    enabled = true
  }

  point_in_time_recovery {
    enabled = false
  }

  deletion_protection_enabled = false
}

data "aws_iam_policy_document" "workbench_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.oidc_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_url}:sub"
      values   = ["system:serviceaccount:workbench:workbench"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "workbench" {
  name               = "otterworks-workbench-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.workbench_trust.json
}

data "aws_iam_policy_document" "workbench_state" {
  statement {
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
      "dynamodb:BatchWriteItem",
      "dynamodb:DescribeTable",
    ]
    resources = [aws_dynamodb_table.workbench_attendee_state.arn]
  }
}

resource "aws_iam_role_policy" "workbench_state" {
  name   = "workbench-attendee-state"
  role   = aws_iam_role.workbench.id
  policy = data.aws_iam_policy_document.workbench_state.json
}
