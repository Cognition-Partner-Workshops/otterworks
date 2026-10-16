data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

data "aws_partition" "current" {}

data "aws_eks_cluster" "this" {
  name = var.eks_cluster
}

data "aws_iam_openid_connect_provider" "eks" {
  url = data.aws_eks_cluster.this.identity[0].oidc[0].issuer
}

data "terraform_remote_state" "otterworks" {
  backend = "s3"

  config = {
    bucket = "otterworks-terraform-state"
    key    = "otterworks/terraform.tfstate"
    region = "us-east-1"
  }
}

locals {
  tags = {
    demo      = "aws-cloud-worker"
    ManagedBy = "terraform"
    owner     = "cloud-worker"
    run_token = var.run_token
    expires   = var.expires
  }

  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name
  partition  = data.aws_partition.current.partition
  oidc_host  = replace(data.aws_eks_cluster.this.identity[0].oidc[0].issuer, "https://", "")

  topic_name      = "otterworks-cw-events"
  queue_name      = "otterworks-cw-notifications"
  dlq_name        = "otterworks-cw-notifications-dlq"
  events_dlq_name = "otterworks-cw-events-dlq"
  table_name      = "otterworks-cw-notifications"
  prefs_name      = "otterworks-cw-notification-preferences"
  alarm_name      = "otterworks-cw-notifications-dlq-depth"
  dashboard_name  = "otterworks-cloud-worker"
  rule_name       = "otterworks-cw-dlq-alarm-to-devin"

  shared       = data.terraform_remote_state.otterworks.outputs
  file_bucket  = local.shared.s3_file_bucket
  dynamodb_arn = "arn:${local.partition}:dynamodb:${local.region}:${local.account_id}:table"
  file_table_arns = [
    "${local.dynamodb_arn}/${local.shared.dynamodb_file_metadata_table}",
    "${local.dynamodb_arn}/${local.shared.dynamodb_folders_table}",
    "${local.dynamodb_arn}/${local.shared.dynamodb_file_versions_table}",
    "${local.dynamodb_arn}/${local.shared.dynamodb_file_shares_table}",
  ]
}
