terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "secret_name" {
  type    = string
  default = "otterworks/etl/runtime"
}

variable "kms_key_arn" {
  description = "Existing customer-managed KMS key ARN; its policy must allow the runtime role to decrypt via Secrets Manager."
  type        = string
}

variable "runtime_role_name" {
  description = "Existing EC2 instance-profile or IRSA role used by the ETL jobs."
  type        = string
}

resource "aws_secretsmanager_secret" "runtime" {
  name                    = var.secret_name
  description             = "ETL database and search credentials; values provisioned outside Terraform"
  kms_key_id              = var.kms_key_arn
  recovery_window_in_days = 30
}

data "aws_iam_policy_document" "runtime_read" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.runtime.arn]
  }

  statement {
    actions   = ["kms:Decrypt"]
    resources = [var.kms_key_arn]

    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["secretsmanager.${var.aws_region}.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "kms:EncryptionContext:SecretARN"
      values   = [aws_secretsmanager_secret.runtime.arn]
    }
  }
}

resource "aws_iam_role_policy" "runtime_read" {
  name   = "otterworks-etl-runtime-read"
  role   = var.runtime_role_name
  policy = data.aws_iam_policy_document.runtime_read.json
}

output "secret_arn" {
  value = aws_secretsmanager_secret.runtime.arn
}
