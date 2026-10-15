# One bounded context of services/legacy-portal carved out of the EC2 monolith (strangler fig):
#
#   client -> HTTP API --ANY <prefix>[/{proxy+}]--> Lambda <run>-<module> (java21, SnapStart alias "live")
#                 |                                   |-- RDS Data API --> Aurora Serverless v2
#                 |                                   '-- PutEvents (announcements only) --> bus, rule
#                 |                                         announcement.published --> SQS + /aws/events log group
#                 '--$default (HTTP proxy)--> ALB of the legacy-portal-ec2 run (every other module, /health, ...)
#
# One state, one HTTP API and one Aurora cluster per run token; the Lambda code is main's port in
# services/legacy-portal-lambda/<module>.
locals {
  name = var.run_token

  modules = {
    announcements = {
      abbr    = "ann"
      prefix  = "/api/announcements"
      schema  = "announcements"
      handler = "com.otterworks.legacyportal.lambda.AnnouncementsHandler::handleRequest"
      events  = true
      # Power tuning with the parity corpus: docs/aws-legacy-portal/announcements-power-tuning.md
      architecture = "arm64"
    }
    preferences = {
      abbr    = "pref"
      prefix  = "/api/preferences"
      schema  = "user_preferences"
      handler = "com.otterworks.legacyportal.lambda.preferences.PreferencesHandler::handleRequest"
      events  = false
      # Not measured yet
      architecture = "x86_64"
    }
    feedback = {
      abbr    = "fb"
      prefix  = "/api/feedback"
      schema  = "feedback"
      handler = "com.otterworks.legacyportal.lambda.feedback.FeedbackHandler::handleRequest"
      events  = false
      # Not measured yet
      architecture = "x86_64"
    }
  }
  m      = local.modules[var.module]
  events = local.m.events

  lambda_architecture = coalesce(var.lambda_architecture, local.m.architecture)

  tags = {
    demo        = "legacy-portal-strangler"
    run_token   = var.run_token
    RunToken    = var.run_token
    Expires     = var.expires
    ManagedBy   = "terraform"
    strangles   = var.ec2_run_token
    bounded_ctx = var.module
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
