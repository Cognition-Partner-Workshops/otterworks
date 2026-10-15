# Every bucket in the storage module must ship server access logs to the
# dedicated access-logs bucket (SonarCloud terraform:S6258).

mock_provider "aws" {
  # The mocked policy document must still be valid JSON for aws_s3_bucket_policy.
  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{}"
    }
  }
}

variables {
  environment = "dev"
  project     = "otterworks"
}

run "all_buckets_log_to_access_logs_bucket" {
  command = apply

  assert {
    condition     = aws_s3_bucket_logging.files.target_bucket == aws_s3_bucket.access_logs.id
    error_message = "files bucket must send server access logs to the access-logs bucket"
  }

  assert {
    condition     = aws_s3_bucket_logging.data_lake.target_bucket == aws_s3_bucket.access_logs.id
    error_message = "data_lake bucket must send server access logs to the access-logs bucket"
  }

  assert {
    condition     = aws_s3_bucket_logging.audit_archive.target_bucket == aws_s3_bucket.access_logs.id
    error_message = "audit_archive bucket must send server access logs to the access-logs bucket"
  }

  assert {
    condition = length(distinct([
      aws_s3_bucket_logging.files.target_prefix,
      aws_s3_bucket_logging.data_lake.target_prefix,
      aws_s3_bucket_logging.audit_archive.target_prefix,
    ])) == 3
    error_message = "each source bucket must log under its own prefix"
  }

  assert {
    condition     = alltrue([for r in aws_s3_bucket_server_side_encryption_configuration.access_logs.rule : alltrue([for d in r.apply_server_side_encryption_by_default : d.sse_algorithm == "AES256"])])
    error_message = "log delivery requires SSE-S3 on the access-logs bucket"
  }

  assert {
    condition     = one(aws_s3_bucket_ownership_controls.access_logs.rule).object_ownership == "BucketOwnerEnforced"
    error_message = "access-logs bucket must disable ACLs and grant log delivery via bucket policy"
  }
}
