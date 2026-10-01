output "storage_aws_iam_user_arn" {
  description = "DESC INTEGRATION LDM_S3_INT -> STORAGE_AWS_IAM_USER_ARN (trusted by the IAM role)."
  value       = local.integration.iam_user_arn
}

output "storage_aws_external_id" {
  description = "DESC INTEGRATION LDM_S3_INT -> STORAGE_AWS_EXTERNAL_ID (sts:ExternalId condition)."
  value       = local.integration.external_id
  sensitive   = true
}

output "integration_role_arn" {
  value = local.role_arn
}

output "allowed_location" {
  value = local.stage_url
}

output "stage" {
  description = "Fully qualified external stage; the job's SNOWFLAKE_STAGE is STG.<stage_name>."
  value       = snowflake_stage_external_s3.ldm.fully_qualified_name
}
