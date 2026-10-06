variable "run_token" {
  description = "Sandbox run token, rs-<yyyymmdd>-<two letters>. Prefixes every resource name."
  type        = string

  validation {
    condition     = can(regex("^rs-[0-9]{8}-[a-z]{2}$", var.run_token))
    error_message = "run_token must look like rs-20261006-ab."
  }
}

variable "expires" {
  description = "RFC 3339 timestamp after which the reaper may delete everything tagged with this run token."
  type        = string

  validation {
    condition     = can(formatdate("YYYY", var.expires))
    error_message = "expires must be an RFC 3339 timestamp such as 2026-10-07T20:00:00Z."
  }
}

variable "aws_region" {
  description = "Region the sandbox runs in."
  type        = string
  default     = "us-east-1"
}

variable "max_receive_count" {
  description = "Receives before an analytics message is dead-lettered (passed to the messaging module)."
  type        = number
  default     = 5
}
