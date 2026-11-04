# Offline guard on the dashboard/runner IRSA policy scope. The AWS provider is
# mocked, so `apply` here only resolves mock values: no credentials, no account:
#   terraform init -backend=false && terraform test

mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = { account_id = "111111111111" }
  }
  mock_data "aws_eks_cluster" {
    defaults = { identity = [{ oidc = [{ issuer = "https://oidc.eks.us-east-1.amazonaws.com/id/TEST" }] }] }
  }
  mock_data "aws_route53_zone" {
    defaults = { zone_id = "ZDEMOZONE" }
  }
  mock_data "aws_iam_openid_connect_provider" {
    defaults = { arn = "arn:aws:iam::111111111111:oidc-provider/token.actions.githubusercontent.com" }
  }
  mock_resource "aws_kms_key" {
    defaults = { arn = "arn:aws:kms:us-east-1:111111111111:key/00000000-0000-0000-0000-000000000000" }
  }
  mock_resource "aws_dynamodb_table" {
    defaults = { arn = "arn:aws:dynamodb:us-east-1:111111111111:table/otterworks-demo-control" }
  }
  mock_resource "aws_secretsmanager_secret" {
    defaults = { arn = "arn:aws:secretsmanager:us-east-1:111111111111:secret:test-AbCdEf" }
  }
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::111111111111:role/test" }
  }
  mock_resource "aws_iam_user" {
    defaults = { arn = "arn:aws:iam::111111111111:user/test" }
  }
  mock_data "aws_iam_policy_document" {
    defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }
}

variables {
  enable_dns = true
}

run "dashboard_policy_is_scoped" {
  command = apply

  # Deploy/teardown edit trust on exactly the shared per-service IRSA roles.
  assert {
    condition = toset(one([for s in data.aws_iam_policy_document.dashboard.statement : s if s.sid == "TenantIrsaTrust"]).resources) == toset([
      for svc in var.tenant_irsa_service_accounts : "arn:aws:iam::111111111111:role/otterworks-${svc}-dev"
    ])
    error_message = "TenantIrsaTrust must list exactly the otterworks-<sa>-<env> tenant service roles."
  }

  # ...and no wildcard that would also match the platform's own roles
  # (otterworks-dev-cluster, otterworks-karpenter-*, otterworks-demo-ops-*, ...).
  assert {
    condition = alltrue(flatten([
      for s in data.aws_iam_policy_document.dashboard.statement : [
        for r in s.resources : !strcontains(r, "*")
      ] if s.effect == "Allow" && length(setintersection(toset(s.actions), toset(["iam:UpdateAssumeRolePolicy", "iam:PassRole", "iam:PutRolePolicy", "iam:AttachRolePolicy"]))) > 0
    ]))
    error_message = "No IAM role-mutation action may be granted on a wildcard role ARN."
  }

  # Record changes are confined to the demo hosted zone.
  assert {
    condition = alltrue(flatten([
      for s in data.aws_iam_policy_document.dashboard.statement : [
        for r in s.resources : r == "arn:aws:route53:::hostedzone/ZDEMOZONE"
      ] if s.effect == "Allow" && contains(s.actions, "route53:ChangeResourceRecordSets")
    ]))
    error_message = "route53:ChangeResourceRecordSets must be scoped to the demo hosted zone only."
  }

  # Shared-bucket GC deletes tenant prefixes; it never reads object contents.
  assert {
    condition     = one([for s in data.aws_iam_policy_document.dashboard.statement : s if s.sid == "SharedBucketObjectGC"]).actions == toset(["s3:DeleteObject"])
    error_message = "SharedBucketObjectGC must grant s3:DeleteObject only."
  }

  # The only object read is the Terraform state bucket (TerraformStateRead).
  assert {
    condition = alltrue(flatten([
      for s in data.aws_iam_policy_document.dashboard.statement : [
        for r in s.resources : r == "arn:aws:s3:::${var.terraform_state_bucket}/*"
      ] if s.effect == "Allow" && contains(s.actions, "s3:GetObject")
    ]))
    error_message = "s3:GetObject may only be granted on the Terraform state bucket."
  }

  # The shared-bucket wildcard also matches the state bucket: deletes there are denied.
  assert {
    condition = length([
      for s in data.aws_iam_policy_document.dashboard.statement : s
      if s.effect == "Deny" && contains(s.actions, "s3:DeleteObject") && contains(s.resources, "arn:aws:s3:::${var.terraform_state_bucket}/*")
    ]) == 1
    error_message = "Object deletes in the Terraform state bucket must be explicitly denied."
  }
}

run "no_dns_no_route53_writes" {
  command = apply

  variables {
    enable_dns = false
  }

  assert {
    condition = length([
      for s in data.aws_iam_policy_document.dashboard.statement : s
      if contains(s.actions, "route53:ChangeResourceRecordSets")
    ]) == 0
    error_message = "Without a demo zone, the dashboard gets no Route53 write access."
  }
}
