# Every bucket in this module must carry a policy that denies non-TLS
# requests (SonarCloud terraform:S6249).

mock_provider "aws" {
  mock_resource "aws_s3_bucket" {
    defaults = {
      arn = "arn:aws:s3:::mock-bucket"
    }
  }
}

variables {
  environment = "dev"
  project     = "otterworks"
}

run "buckets_deny_insecure_transport" {
  command = apply

  assert {
    condition     = aws_s3_bucket_policy.files.bucket == aws_s3_bucket.files.id
    error_message = "files bucket has no HTTPS-only bucket policy"
  }

  assert {
    condition     = aws_s3_bucket_policy.data_lake.bucket == aws_s3_bucket.data_lake.id
    error_message = "data_lake bucket has no HTTPS-only bucket policy"
  }

  assert {
    condition     = aws_s3_bucket_policy.audit_archive.bucket == aws_s3_bucket.audit_archive.id
    error_message = "audit_archive bucket has no HTTPS-only bucket policy"
  }

  assert {
    condition = alltrue([
      for policy in [
        aws_s3_bucket_policy.files.policy,
        aws_s3_bucket_policy.data_lake.policy,
        aws_s3_bucket_policy.audit_archive.policy,
        ] : anytrue([
          for statement in jsondecode(policy).Statement :
          statement.Effect == "Deny" &&
          statement.Principal == "*" &&
          statement.Action == "s3:*" &&
          try(statement.Condition.Bool["aws:SecureTransport"], null) == "false" &&
          contains(statement.Resource, "arn:aws:s3:::mock-bucket") &&
          contains(statement.Resource, "arn:aws:s3:::mock-bucket/*")
      ])
    ])
    error_message = "every bucket policy must deny s3:* for all principals on the bucket and its objects when aws:SecureTransport is false"
  }
}
