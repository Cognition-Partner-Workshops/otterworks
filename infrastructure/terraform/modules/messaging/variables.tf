variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "project" {
  description = "Project name used as prefix for resource naming"
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,20}$", var.project))
    error_message = "Project name must be lowercase alphanumeric with hyphens, 2-21 characters."
  }
}

variable "max_receive_count" {
  description = "Receives before an analytics or search-indexing message moves to its dead-letter queue. The notifications queue keeps 3."
  type        = number
  default     = 5

  validation {
    condition     = var.max_receive_count >= 1 && var.max_receive_count <= 1000 && floor(var.max_receive_count) == var.max_receive_count
    error_message = "max_receive_count must be an integer from 1 to 1000."
  }
}

variable "oldest_message_age_alarm_seconds" {
  description = "ApproximateAgeOfOldestMessage threshold for the source-queue backlog alarms."
  type        = number
  default     = 3600
}

variable "alarm_actions" {
  description = "ARNs notified when a DLQ or backlog alarm changes state. Empty keeps the alarms visible without paging anyone."
  type        = list(string)
  default     = []
  nullable    = false
}
