# Guards terraform:S6327 (Amazon SNS topics should be encrypted at rest):
# the shared events topic must carry the module's KMS key so messages are
# never stored in plaintext. Runs offline against a mocked AWS provider.

mock_provider "aws" {
  mock_resource "aws_kms_key" {
    defaults = {
      arn    = "arn:aws:kms:us-east-1:123456789012:key/11111111-2222-3333-4444-555555555555"
      key_id = "11111111-2222-3333-4444-555555555555"
    }
  }

  mock_resource "aws_sns_topic" {
    defaults = {
      arn = "arn:aws:sns:us-east-1:123456789012:otterworks-events-dev"
    }
  }

  mock_resource "aws_sqs_queue" {
    defaults = {
      arn = "arn:aws:sqs:us-east-1:123456789012:otterworks-queue-dev"
      id  = "https://sqs.us-east-1.amazonaws.com/123456789012/otterworks-queue-dev"
      url = "https://sqs.us-east-1.amazonaws.com/123456789012/otterworks-queue-dev"
    }
  }

  mock_data "aws_caller_identity" {
    defaults = {
      account_id = "123456789012"
    }
  }

  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}"
    }
  }
}

variables {
  environment = "dev"
  project     = "otterworks"
}

run "events_topic_is_encrypted_at_rest" {
  command = apply

  assert {
    condition     = aws_sns_topic.events.kms_master_key_id != null && aws_sns_topic.events.kms_master_key_id != ""
    error_message = "aws_sns_topic.events must set kms_master_key_id; omitting it disables SNS server-side encryption (terraform:S6327)."
  }

  assert {
    condition     = aws_sns_topic.events.kms_master_key_id == aws_kms_key.events.arn
    error_message = "aws_sns_topic.events must be encrypted with the messaging module's own KMS key."
  }

  assert {
    condition     = aws_kms_key.events.enable_key_rotation == true
    error_message = "The SNS events KMS key must have automatic rotation enabled."
  }

  assert {
    condition     = output.events_topic_kms_key_arn == aws_kms_key.events.arn
    error_message = "events_topic_kms_key_arn must expose the key so publisher IRSA roles can be granted kms:GenerateDataKey/kms:Decrypt."
  }
}
