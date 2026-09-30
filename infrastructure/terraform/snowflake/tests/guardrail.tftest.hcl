# terraform test (offline, mocked providers): the integration role's S3 policy names exactly one tenant prefix.
#   terraform -chdir=infrastructure/terraform/snowflake init -backend=false && terraform ... test

mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = { account_id = "599083837640" }
  }
  mock_data "aws_partition" {
    defaults = { partition = "aws" }
  }
}

mock_provider "snowflake" {
  mock_resource "snowflake_storage_integration_aws" {
    defaults = {
      describe_output = [{
        iam_user_arn             = "arn:aws:iam::123456789012:user/sf-example"
        external_id              = "EXAMPLE_SFCRole=1_abc="
        allowed_locations        = []
        blocked_locations        = []
        comment                  = ""
        enabled                  = true
        id                       = ""
        object_acl               = ""
        provider                 = "S3"
        role_arn                 = ""
        use_privatelink_endpoint = false
      }]
    }
  }
  mock_resource "snowflake_stage_external_s3" {
    defaults = { fully_qualified_name = "\"OTTERWORKS_LDM_S30_AFTER\".\"STG\".\"LDM_STAGE\"" }
  }
}

run "policy_names_exactly_one_prefix" {
  # apply against the mocks: the trust policy depends on describe_output, which is only known after create
  command = apply

  assert {
    condition = toset(flatten([
      for s in jsondecode(aws_iam_role_policy.snowflake_s3.policy).Statement : s.Resource if contains(s.Action, "s3:GetObject")
    ])) == toset(["arn:aws:s3:::otterworks-ldm-s30-after-599083837640/s30-after/*"])
    error_message = "object statement must name exactly the s30-after/ prefix"
  }

  assert {
    condition = toset(flatten([
      for s in jsondecode(aws_iam_role_policy.snowflake_s3.policy).Statement : s.Condition.StringLike["s3:prefix"] if contains(s.Action, "s3:ListBucket")
    ])) == toset(["s30-after/*"])
    error_message = "ListBucket must be conditioned on exactly s30-after/*"
  }

  assert {
    condition = alltrue([
      for s in jsondecode(aws_iam_role_policy.snowflake_s3.policy).Statement : alltrue([
        for r in s.Resource : r == "arn:aws:s3:::otterworks-ldm-s30-after-599083837640" || r == "arn:aws:s3:::otterworks-ldm-s30-after-599083837640/s30-after/*"
      ])
    ])
    error_message = "no statement may name any other bucket or prefix"
  }

  assert {
    condition     = !anytrue([for s in jsondecode(aws_iam_role_policy.snowflake_s3.policy).Statement : contains(s.Action, "s3:PutObject")])
    error_message = "Snowflake only reads and purges; it never writes to the tenant prefix"
  }

  assert {
    condition     = toset(snowflake_storage_integration_aws.ldm.storage_allowed_locations) == toset(["s3://otterworks-ldm-s30-after-599083837640/s30-after/"])
    error_message = "LDM_S3_INT must allow exactly the tenant prefix"
  }

  assert {
    condition     = length(jsondecode(aws_iam_role.snowflake.assume_role_policy).Statement) == 1
    error_message = "steady state: Snowflake's IAM user is the only trusted principal"
  }

  assert {
    condition     = jsondecode(aws_iam_role.snowflake.assume_role_policy).Statement[0].Condition.StringEquals["sts:ExternalId"] == "EXAMPLE_SFCRole=1_abc="
    error_message = "trust must be pinned to the integration's STORAGE_AWS_EXTERNAL_ID"
  }
}

run "prefix_must_be_a_single_segment" {
  command = plan

  variables {
    prefix = "s30-after/../s29-after/"
  }

  expect_failures = [var.prefix]
}

run "whole_bucket_is_rejected" {
  command = plan

  variables {
    prefix = "/"
  }

  expect_failures = [var.prefix]
}
