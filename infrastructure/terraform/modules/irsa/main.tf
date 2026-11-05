# ------------------------------------------------------------------------------
# OtterWorks IRSA Module
# IAM Roles for Service Accounts (IRSA) on EKS
# Enables fine-grained AWS permissions per Kubernetes service account
# ------------------------------------------------------------------------------

locals {
  common_tags = {
    Module  = "irsa"
    Project = var.project
  }
}

data "aws_iam_policy_document" "assume_role" {
  for_each = var.service_accounts

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    # Exact service-account match only. Tenant namespaces (otterworks-<id>) never
    # assume these shared roles: deploy-tenant.sh mints a per-tenant role whose
    # trust names that namespace alone and whose S3 access is limited to the
    # tenant's prefix. A wildcard here would let any tenant's code act on every
    # tenant's data.
    condition {
      test     = "StringEquals"
      variable = "${replace(var.oidc_provider_url, "https://", "")}:sub"
      values = [
        for ns in concat([var.namespace], var.additional_namespaces) :
        "system:serviceaccount:${ns}:${each.key}"
      ]
    }

    condition {
      test     = "StringEquals"
      variable = "${replace(var.oidc_provider_url, "https://", "")}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "service_account" {
  for_each = var.service_accounts

  name               = "${var.project}-${each.key}-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.assume_role[each.key].json

  tags = merge(local.common_tags, {
    Service            = each.key
    ServiceAccountName = each.key
  })
}

resource "aws_iam_role_policy" "service_account" {
  for_each = var.service_accounts

  name   = "${var.project}-${each.key}-policy"
  role   = aws_iam_role.service_account[each.key].id
  policy = each.value
}
