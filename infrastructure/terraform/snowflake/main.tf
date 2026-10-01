# Snowflake reads the job's Parquet load batches straight from the tenant's S3 staging prefix:
#   STORAGE INTEGRATION LDM_S3_INT (allowed location s3://<bucket>/<prefix>) -> IAM role trusted by the
#   integration's Snowflake IAM user + external ID -> external stage <database>.STG.LDM_STAGE on that prefix.
# Two-step apply (README.md): the trust policy needs STORAGE_AWS_IAM_USER_ARN / STORAGE_AWS_EXTERNAL_ID, which
# Snowflake only generates once the integration exists.

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  namespace       = trimsuffix(var.prefix, "/")
  token           = upper(replace(local.namespace, "-", "_"))
  job_role        = var.job_role != "" ? var.job_role : "LDM_JOB_${local.token}"
  sf_organization = split("-", var.account)[0]
  sf_account      = split("-", var.account)[1]

  role_name  = "otterworks-ldm-${local.namespace}-snowflake"
  role_arn   = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:role/${local.role_name}"
  bucket_arn = "arn:${data.aws_partition.current.partition}:s3:::${var.bucket}"
  stage_url  = "s3://${var.bucket}/${var.prefix}"

  # The one tenant prefix the integration role may touch; guarded by check "single_tenant_prefix".
  object_resources = ["${local.bucket_arn}/${var.prefix}*"]
  list_prefixes    = ["${var.prefix}*"]

  s3_policy = {
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "ListTenantPrefix"
        Effect    = "Allow"
        Action    = ["s3:ListBucket"]
        Resource  = [local.bucket_arn]
        Condition = { StringLike = { "s3:prefix" = local.list_prefixes } }
      },
      {
        Sid      = "BucketLocation"
        Effect   = "Allow"
        Action   = ["s3:GetBucketLocation"]
        Resource = [local.bucket_arn]
      },
      {
        # Read the batch; Delete for COPY INTO ... PURGE = TRUE. No PutObject: Snowflake never writes here.
        Sid      = "ReadPurgeTenantObjects"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:GetObjectVersion", "s3:DeleteObject", "s3:DeleteObjectVersion"]
        Resource = local.object_resources
      },
    ]
  }

  integration = one(snowflake_storage_integration_aws.ldm.describe_output)

  tags = {
    owner     = "otterworks-demo"
    demo      = "legacy-data-migration"
    namespace = local.namespace
  }
}

resource "snowflake_storage_integration_aws" "ldm" {
  name                      = var.integration_name
  enabled                   = true
  storage_provider          = "S3"
  storage_allowed_locations = [local.stage_url]
  storage_aws_role_arn      = local.role_arn
  comment                   = "otterworks ldm ${local.namespace}: COPY INTO from ${local.stage_url} (Terraform: infrastructure/terraform/snowflake)"
}

resource "aws_iam_role" "snowflake" {
  name                 = local.role_name
  description          = "Snowflake storage integration ${var.integration_name}: read/purge ${local.stage_url} only"
  max_session_duration = 3600
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [{
        Sid       = "SnowflakeStorageIntegration"
        Effect    = "Allow"
        Action    = "sts:AssumeRole"
        Principal = { AWS = local.integration.iam_user_arn }
        Condition = { StringEquals = { "sts:ExternalId" = local.integration.external_id } }
      }],
      [for arn in var.guardrail_principal_arns : {
        Sid       = "GuardrailProof${index(var.guardrail_principal_arns, arn)}"
        Effect    = "Allow"
        Action    = "sts:AssumeRole"
        Principal = { AWS = arn }
        Condition = { StringEquals = { "sts:ExternalId" = local.integration.external_id } }
      }],
    )
  })
}

resource "aws_iam_role_policy" "snowflake_s3" {
  name   = "tenant-prefix-read-purge"
  role   = aws_iam_role.snowflake.id
  policy = jsonencode(local.s3_policy)

  lifecycle {
    precondition {
      condition     = length(local.object_resources) == 1 && length(local.list_prefixes) == 1
      error_message = "The Snowflake integration role must be scoped to exactly one tenant prefix."
    }
  }
}

check "single_tenant_prefix" {
  assert {
    condition = (
      toset(flatten([for s in jsondecode(aws_iam_role_policy.snowflake_s3.policy).Statement : s.Resource if s.Sid == "ReadPurgeTenantObjects"])) == toset(["${local.bucket_arn}/${var.prefix}*"])
      && toset(flatten([for s in jsondecode(aws_iam_role_policy.snowflake_s3.policy).Statement : s.Condition.StringLike["s3:prefix"] if s.Sid == "ListTenantPrefix"])) == toset(["${var.prefix}*"])
      && alltrue([for s in jsondecode(aws_iam_role_policy.snowflake_s3.policy).Statement : alltrue([for r in s.Resource : r == local.bucket_arn || r == "${local.bucket_arn}/${var.prefix}*"])])
    )
    error_message = "Integration role policy must allow exactly one object prefix (${var.prefix}) and list only under it."
  }
  assert {
    condition     = toset(snowflake_storage_integration_aws.ldm.storage_allowed_locations) == toset([local.stage_url])
    error_message = "LDM_S3_INT must allow exactly ${local.stage_url}."
  }
}

resource "snowflake_stage_external_s3" "ldm" {
  name                = var.stage_name
  database            = var.database
  schema              = "STG"
  url                 = local.stage_url
  storage_integration = snowflake_storage_integration_aws.ldm.name
  comment             = "ldm load batches (Parquet) read from ${local.stage_url}; COPY INTO ... PURGE = TRUE removes them"

  file_format {
    parquet {
      use_logical_type = "true"
      binary_as_text   = "false"
    }
  }

  # Stage creation does not touch S3, but the first COPY does: order it after the role and its policy.
  depends_on = [aws_iam_role_policy.snowflake_s3]
}

# The job role only gets USAGE on this one stage, not on the integration, so it cannot point a stage of its own at
# any other location the integration allows.
resource "snowflake_grant_privileges_to_account_role" "job_stage_usage" {
  account_role_name = local.job_role
  privileges        = ["USAGE"]
  on_schema_object {
    object_type = "STAGE"
    object_name = snowflake_stage_external_s3.ldm.fully_qualified_name
  }
}
