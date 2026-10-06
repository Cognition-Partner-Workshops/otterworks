# ------------------------------------------------------------------------------
# "Before" twin of the reliability sandbox: the messaging module exactly as it
# was at c2332d0e, where analytics_events and search_indexing had no
# dead-letter queue. Same tags, its own local state and a "-b" name suffix, so
# it can run next to the repaired sandbox for the same token.
# ------------------------------------------------------------------------------

variable "run_token" {
  description = "Sandbox run token, rs-<yyyymmdd>-<two letters>."
  type        = string

  validation {
    condition     = can(regex("^rs-[0-9]{8}-[a-z]{2}$", var.run_token))
    error_message = "run_token must look like rs-20261006-ab."
  }
}

variable "expires" {
  description = "RFC 3339 expiry for the reaper."
  type        = string

  validation {
    condition     = can(formatdate("YYYY", var.expires))
    error_message = "expires must be an RFC 3339 timestamp such as 2026-10-07T20:00:00Z."
  }
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      run_token = var.run_token
      Expires   = var.expires
      Project   = "otterworks-reliability-sandbox"
      ManagedBy = "terraform"
      Layer     = "sandbox-before"
    }
  }
}

module "messaging" {
  source = "git::https://github.com/Cognition-Partner-Workshops/otterworks.git//infrastructure/terraform/modules/messaging?ref=c2332d0ed9e72b013f0c9d966d4b05b3e2ea0a03"

  project     = "${var.run_token}-b"
  environment = "dev"
}

output "run_token" {
  value = var.run_token
}

output "region" {
  value = var.aws_region
}

output "events_topic_arn" {
  value = module.messaging.events_topic_arn
}

output "analytics_queue_url" {
  value = module.messaging.analytics_queue_url
}

output "analytics_queue_arn" {
  value = module.messaging.analytics_queue_arn
}
