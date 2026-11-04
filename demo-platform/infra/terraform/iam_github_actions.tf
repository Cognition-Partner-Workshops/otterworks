# The identity GitHub Actions uses to ship tenant environments.
#
# Continuous delivery needs to do two things: push service images to ECR, and
# tell the Demo Ops dashboard to redeploy the tenant that owns the branch. It
# deliberately gets no more than that -- no EKS, no RDS, no control-table
# writes -- because the dashboard's runner Job already holds that authority
# under its own IRSA role, behind validation and an audit trail.
#
# Two roles, because the code a workflow runs is whatever the pushed branch
# says it is:
#   otterworks-github-actions         main only. Moves the golden `main` tag and
#                                     reads the dashboard passcode.
#   otterworks-github-actions-branch  workshop-*/demo-*. Pushes new immutable
#                                     build tags and nothing else: it cannot
#                                     delete or re-point a tag (the repositories
#                                     are IMMUTABLE, and BatchDeleteImage is
#                                     denied) and cannot read the passcode. Its
#                                     deploy goes to the dashboard with a GitHub
#                                     OIDC token instead (/api/cd/deploy), which
#                                     checks the branch owns the tenant.
#
# Federated (OIDC) rather than an IAM user: a workflow exchanges a short-lived
# GitHub token for equally short-lived AWS credentials, so there is no static
# key to leak, store in a repo secret, or rotate.

data "aws_iam_openid_connect_provider" "github" {
  count = var.enable_github_actions_role ? 1 : 0
  url   = "https://token.actions.githubusercontent.com"
}

data "aws_iam_policy_document" "github_actions_trust" {
  count = var.enable_github_actions_role ? 1 : 0

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github[0].arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # This repository's main and nothing else. This role moves the golden
    # `main` image every tenant falls back to and reads the dashboard passcode,
    # so it must never be reachable from a branch an attendee can push to:
    # those get the branch role below. `pull_request`, `environment` and tag
    # subjects are excluded by the same token: a fork PR never gets
    # credentials, and neither does a pushed tag (release builds run from main
    # via workflow_dispatch -- see .github/workflows/docker-build.yml).
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_actions_main_repo}:ref:refs/heads/main"]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  count = var.enable_github_actions_role ? 1 : 0

  name               = "otterworks-github-actions"
  description        = "GitHub Actions CD for main: publish the golden images and redeploy t-main"
  assume_role_policy = data.aws_iam_policy_document.github_actions_trust[0].json

  # A workflow run is minutes; anything longer is only useful to a stolen token.
  max_session_duration = 3600

  tags = {
    Purpose = "Continuous delivery for demo tenants"
  }
}

data "aws_iam_policy_document" "github_actions" {
  count = var.enable_github_actions_role ? 1 : 0

  # ECR authorization is account-wide by API design (GetAuthorizationToken takes
  # no resource), so the repository-level grants below are what actually scope
  # this role's push access.
  statement {
    sid       = "EcrAuth"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid    = "EcrPushPull"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchDeleteImage",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImages",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = ["arn:aws:ecr:${var.aws_region}:${data.aws_caller_identity.current.account_id}:repository/${var.ecr_repo_prefix}/*"]
  }

  # The same grant the provisioner user holds: read the dashboard passcode, and
  # nothing else. Everything CD does to a tenant goes through the dashboard's
  # HTTPS API, authenticated with that passcode.
  statement {
    sid       = "ReadDashboardPasscode"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
    resources = [aws_secretsmanager_secret.dashboard_passcode.arn]
  }

  statement {
    sid       = "DecryptDashboardPasscode"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [aws_kms_key.dashboard_passcode.arn]

    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["secretsmanager.${var.aws_region}.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "github_actions" {
  count = var.enable_github_actions_role ? 1 : 0

  name   = "cd-access"
  role   = aws_iam_role.github_actions[0].id
  policy = data.aws_iam_policy_document.github_actions[0].json
}

data "aws_iam_policy_document" "github_actions_branch_trust" {
  count = var.enable_github_actions_role ? 1 : 0

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github[0].arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = flatten([
        for repo, refs in var.github_actions_branch_repos :
        [for ref in refs : "repo:${repo}:ref:refs/heads/${ref}"]
      ])
    }
  }
}

resource "aws_iam_role" "github_actions_branch" {
  count = var.enable_github_actions_role ? 1 : 0

  name                 = "otterworks-github-actions-branch"
  description          = "GitHub Actions CD for workshop-*/demo-* branches: push immutable build tags only"
  assume_role_policy   = data.aws_iam_policy_document.github_actions_branch_trust[0].json
  max_session_duration = 3600

  tags = {
    Purpose = "Continuous delivery for demo tenants (branch builds)"
  }
}

data "aws_iam_policy_document" "github_actions_branch" {
  count = var.enable_github_actions_role ? 1 : 0

  statement {
    sid       = "EcrAuth"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  # Push a new image under a new tag, and read back what exists (the workflow
  # skips rebuilding a commit already in the registry). PutImage cannot move an
  # existing tag in an IMMUTABLE repository, and without BatchDeleteImage there
  # is no way to free one up first.
  statement {
    sid    = "EcrPushNewTags"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImages",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = ["arn:aws:ecr:${var.aws_region}:${data.aws_caller_identity.current.account_id}:repository/${var.ecr_repo_prefix}/*"]
  }

  # Belt and braces against a later grant widening this role by accident.
  statement {
    sid    = "DenyTagMovesAndSecrets"
    effect = "Deny"
    actions = [
      "ecr:BatchDeleteImage",
      "ecr:PutImageTagMutability",
      "ecr:SetRepositoryPolicy",
      "ecr:DeleteRepository",
      "secretsmanager:*",
      "kms:Decrypt",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "github_actions_branch" {
  count = var.enable_github_actions_role ? 1 : 0

  name   = "cd-branch-access"
  role   = aws_iam_role.github_actions_branch[0].id
  policy = data.aws_iam_policy_document.github_actions_branch[0].json
}
