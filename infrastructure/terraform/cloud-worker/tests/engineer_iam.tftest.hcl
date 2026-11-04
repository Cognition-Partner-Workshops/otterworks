# Offline check of the devin-aws-engineer guardrails: mocked providers, no AWS calls.
#   terraform init -backend=false && terraform test

mock_provider "aws" {
  override_data {
    target = data.aws_caller_identity.current
    values = { account_id = "123456789012" }
  }
  override_data {
    target = data.aws_partition.current
    values = { partition = "aws" }
  }
  override_data {
    target = data.aws_region.current
    values = { name = "us-east-1" }
  }
  override_data {
    target = data.aws_eks_cluster.this
    values = { identity = [{ oidc = [{ issuer = "https://oidc.eks.us-east-1.amazonaws.com/id/EXAMPLE" }] }] }
  }
  override_data {
    target = data.aws_iam_openid_connect_provider.eks
    values = { arn = "arn:aws:iam::123456789012:oidc-provider/oidc.eks.us-east-1.amazonaws.com/id/EXAMPLE" }
  }

  mock_data "aws_iam_policy_document" {
    defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }
  mock_resource "aws_iam_policy" {
    defaults = { arn = "arn:aws:iam::123456789012:policy/devin-aws-engineer-boundary" }
  }
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::123456789012:role/devin-cw-builder" }
  }
  mock_resource "aws_iam_user" {
    defaults = { arn = "arn:aws:iam::123456789012:user/devin-cw-reader" }
  }
  mock_resource "aws_sns_topic" {
    defaults = { arn = "arn:aws:sns:us-east-1:123456789012:otterworks-cw-events" }
  }
  mock_resource "aws_sqs_queue" {
    defaults = { arn = "arn:aws:sqs:us-east-1:123456789012:otterworks-cw-notifications" }
  }
  mock_resource "aws_dynamodb_table" {
    defaults = { arn = "arn:aws:dynamodb:us-east-1:123456789012:table/otterworks-cw-notifications" }
  }
  mock_resource "aws_cloudwatch_metric_alarm" {
    defaults = { arn = "arn:aws:cloudwatch:us-east-1:123456789012:alarm:otterworks-cw-notifications-dlq-depth" }
  }
  mock_resource "aws_cloudwatch_event_connection" {
    defaults = { arn = "arn:aws:events:us-east-1:123456789012:connection/otterworks-cw-devin-webhook/x" }
  }
  mock_resource "aws_cloudwatch_event_api_destination" {
    defaults = { arn = "arn:aws:events:us-east-1:123456789012:api-destination/otterworks-cw-devin-webhook/x" }
  }
  mock_resource "aws_cloudwatch_event_rule" {
    defaults = { arn = "arn:aws:events:us-east-1:123456789012:rule/otterworks-cw-dlq-alarm-to-devin" }
  }
}

mock_provider "kubernetes" {}
mock_provider "helm" {}

override_data {
  target = data.terraform_remote_state.otterworks
  values = {
    outputs = {
      s3_file_bucket               = "otterworks-files"
      dynamodb_file_metadata_table = "file-metadata"
      dynamodb_folders_table       = "folders"
      dynamodb_file_versions_table = "file-versions"
      dynamodb_file_shares_table   = "file-shares"
    }
  }
}

run "engineer_guardrails" {
  command = apply

  assert {
    condition     = aws_iam_role.devin_builder.permissions_boundary == aws_iam_policy.devin_engineer_boundary.arn
    error_message = "devin-cw-builder must carry the engineer boundary, since the engineer may attach lp-* policies to it."
  }

  assert {
    condition = alltrue([
      for s in jsondecode(aws_iam_role_policy.devin_engineer_iam.policy).Statement :
      s.Effect == "Deny" || length([for r in flatten([try(s.Resource, [])]) : r if strcontains(r, ":role/otterworks-") || strcontains(r, ":policy/otterworks-")]) == 0
    ])
    error_message = "The engineer must not be granted IAM writes on otterworks-* roles or policies (shared with platform roles)."
  }

  assert {
    condition = alltrue([
      for s in jsondecode(aws_iam_role_policy.devin_engineer_iam.policy).Statement :
      try(s.Condition.StringEquals["iam:PermissionsBoundary"], "") == aws_iam_policy.devin_engineer_boundary.arn
      if s.Effect == "Allow" && length(setintersection(toset(flatten([try(s.Action, [])])), toset(["iam:CreateRole", "iam:PutRolePolicy", "iam:AttachRolePolicy", "iam:UpdateAssumeRolePolicy"]))) > 0
    ])
    error_message = "Every allow of CreateRole, PutRolePolicy, AttachRolePolicy or UpdateAssumeRolePolicy must require the engineer boundary."
  }

  assert {
    condition = anytrue([
      for s in jsondecode(aws_iam_role_policy.devin_engineer_iam.policy).Statement :
      s.Effect == "Deny" && contains(flatten([try(s.Action, [])]), "iam:CreateRole") && try(s.Condition.StringNotEquals["iam:PermissionsBoundary"], "") == aws_iam_policy.devin_engineer_boundary.arn
    ])
    error_message = "An explicit deny must block role writes without the engineer boundary."
  }

  assert {
    condition = anytrue([
      for s in jsondecode(aws_iam_role_policy.devin_engineer_iam.policy).Statement :
      s.Effect == "Deny" && contains(flatten([try(s.Action, [])]), "iam:AttachRolePolicy") && length(try(flatten([s.Condition.ArnNotLike["iam:PolicyARN"]]), [])) > 0 && !contains(try(flatten([s.Condition.ArnNotLike["iam:PolicyARN"]]), []), "arn:aws:iam::aws:policy/AdministratorAccess")
    ])
    error_message = "An explicit deny must block attaching any policy outside the allow-list (AdministratorAccess included)."
  }

  assert {
    condition = anytrue([
      for s in jsondecode(aws_iam_role_policy.devin_engineer_iam.policy).Statement :
      s.Effect == "Deny" && contains(flatten([try(s.Resource, [])]), "arn:aws:iam::123456789012:role/devin-*")
    ])
    error_message = "An explicit deny must protect the devin-* roles."
  }

  assert {
    condition = anytrue([
      for s in jsondecode(aws_iam_role_policy.devin_engineer_iam.policy).Statement :
      s.Effect == "Deny" && contains(flatten([try(s.Resource, [])]), aws_iam_policy.devin_engineer_boundary.arn) && contains(flatten([try(s.Resource, [])]), "arn:aws:iam::123456789012:user/*")
    ])
    error_message = "An explicit deny must protect the boundary policy and IAM users."
  }

  assert {
    condition = alltrue([
      for s in jsondecode(aws_iam_policy.devin_engineer_boundary.policy).Statement :
      s.Effect == "Deny" || (contains(flatten([try(s.NotAction, [])]), "iam:*") || alltrue([for a in flatten([try(s.Action, [])]) : startswith(a, "iam:Get") || startswith(a, "iam:List") || startswith(a, "iam:Simulate")]))
    ])
    error_message = "The boundary must allow no IAM writes."
  }
}
