# Offline checks for two control-plane guardrails (mocked provider, no AWS calls).
# Run: terraform init -backend=false && terraform test

mock_provider "aws" {
  override_data {
    target = data.aws_caller_identity.current
    values = {
      account_id = "111111111111"
    }
  }

  override_data {
    target = data.aws_eks_cluster.this
    values = {
      identity = [{ oidc = [{ issuer = "https://oidc.eks.us-east-1.amazonaws.com/id/EXAMPLE" }] }]
    }
  }

  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}"
    }
  }

  mock_resource "aws_kms_key" {
    defaults = {
      arn = "arn:aws:kms:us-east-1:111111111111:key/00000000-0000-0000-0000-000000000000"
    }
  }

  mock_resource "aws_dynamodb_table" {
    defaults = {
      arn = "arn:aws:dynamodb:us-east-1:111111111111:table/otterworks-demo-control"
    }
  }

  mock_resource "aws_secretsmanager_secret" {
    defaults = {
      arn = "arn:aws:secretsmanager:us-east-1:111111111111:secret:otterworks-demo-passcode"
    }
  }

  mock_resource "aws_iam_role" {
    defaults = {
      arn = "arn:aws:iam::111111111111:role/otterworks-demo-ops-dashboard-dev"
    }
  }

  mock_resource "aws_iam_user" {
    defaults = {
      arn = "arn:aws:iam::111111111111:user/de-demo-provisioner"
    }
  }
}

run "null_budget_emails_mean_no_budget" {
  command = plan

  variables {
    budget_alert_emails = null
  }

  assert {
    condition     = length(aws_budgets_budget.monthly) == 0
    error_message = "A null address list must behave like an empty one, not crash the plan."
  }
}

run "budget_created_when_addresses_given" {
  command = plan

  variables {
    budget_alert_emails = ["ops@example.com"]
  }

  assert {
    condition     = length(aws_budgets_budget.monthly) == 1
    error_message = "A non-empty address list creates the budget."
  }
}

run "live_cluster_nodes_are_never_terminable" {
  command = plan

  variables {
    sweepable_clusters = ["otterworks-dev", "otterworks-old"]
  }

  assert {
    condition = alltrue([
      for s in data.aws_iam_policy_document.dashboard.statement :
      !(contains(coalesce(s.actions, []), "ec2:TerminateInstances") && anytrue([for c in coalesce(s.condition, []) : c.variable == "aws:ResourceTag/kubernetes.io/cluster/otterworks-dev"]))
    ])
    error_message = "Listing the live cluster in sweepable_clusters must not grant terminate on its nodes."
  }

  assert {
    condition = anytrue([
      for s in data.aws_iam_policy_document.dashboard.statement :
      contains(coalesce(s.actions, []), "ec2:TerminateInstances") && anytrue([for c in coalesce(s.condition, []) : c.variable == "aws:ResourceTag/kubernetes.io/cluster/otterworks-old"])
    ])
    error_message = "A previous cluster name still gets the Karpenter terminate grant."
  }
}
