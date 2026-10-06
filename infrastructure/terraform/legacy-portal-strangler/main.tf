# Announcements bounded context of services/legacy-portal, carved out of the EC2 monolith:
#
#   client -> HTTP API --ANY /api/announcements[/{proxy+}]--> Lambda (java21, SnapStart alias "live")
#                 |                                             |-- RDS Data API --> Aurora Serverless v2
#                 |                                             '-- PutEvents ----> event bus
#                 |                                                   rule announcement.published --> SQS (notifications)
#                 |                                                                            '--> /aws/events log group
#                 '--$default (HTTP proxy)--> ALB of the legacy-portal-ec2 run (preferences, feedback, /health, ...)
locals {
  name = var.run_token

  tags = {
    demo        = "legacy-portal-announcements"
    run_token   = var.run_token
    RunToken    = var.run_token
    Expires     = var.expires
    ManagedBy   = "terraform"
    strangles   = var.ec2_run_token
    bounded_ctx = "announcements"
  }
}

data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

data "aws_vpc" "this" {
  tags = { Name = var.vpc_name }
}

data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.this.id]
  }

  filter {
    name   = "tag:Name"
    values = ["${var.private_subnet_name_prefix}*"]
  }
}

# The EC2 monolith is not managed here; only its ALB DNS name is read.
data "aws_lb" "ec2" {
  name = var.ec2_run_token
}
