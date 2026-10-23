variable "service_name" {
  description = "Lowercase identifier for the application being rehosted."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,30}$", var.service_name))
    error_message = "service_name must start with a lowercase letter and contain 2 to 31 lowercase letters, digits, or hyphens."
  }
}

variable "run_token" {
  description = "Unique run identifier used for names and mandatory run tags."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]*-[0-9]{8}-[a-z0-9]{2}$", var.run_token)) && length(var.run_token) <= 28
    error_message = "run_token must match <prefix>-YYYYMMDD-xx and be at most 28 characters so ALB and target group names fit AWS limits."
  }
}

variable "expires" {
  description = "RFC 3339 expiry timestamp applied to the Expires tag."
  type        = string

  validation {
    condition     = can(formatdate("YYYY", var.expires))
    error_message = "expires must be a valid RFC 3339 timestamp."
  }
}

variable "disposition_evidence" {
  description = "Assessment row that supports this rehost disposition."
  type        = string

  validation {
    condition     = trimspace(var.disposition_evidence) != ""
    error_message = "disposition_evidence must identify the assessment row."
  }
}

variable "vpc_id" {
  description = "Existing VPC hosting the ALB and instance."
  type        = string
}

variable "subnet_ids" {
  description = "Existing public subnet IDs; the ALB uses all subnets and the instance uses the first."
  type        = list(string)

  validation {
    condition     = length(var.subnet_ids) > 0
    error_message = "subnet_ids must contain at least one subnet."
  }
}

variable "extra_tags" {
  description = "Additional tags; mandatory disposition tags take precedence."
  type        = map(string)
  default     = {}
}

variable "instance_type" {
  description = "EC2 instance type."
  type        = string
  default     = "t3.small"
}

variable "ami_id" {
  description = "Optional AMI override. When null, the current AL2023 x86_64 SSM parameter is read."
  type        = string
  default     = null
}

variable "app_port" {
  description = "Port served by the application."
  type        = number
  default     = 8080
}

variable "health_check_path" {
  description = "HTTP path used by the ALB target health check."
  type        = string
  default     = "/health"
}

variable "artifact_path" {
  description = "Absolute or path.root-relative artifact file to upload."
  type        = string
}

variable "artifact_name" {
  description = "Object key for the uploaded artifact; defaults to the artifact file basename."
  type        = string
  default     = null
}

variable "packages" {
  description = "Additional packages to install with dnf before bootstrap."
  type        = list(string)
  default     = []
}

variable "start_command" {
  description = "Systemd ExecStart command. The artifact is at /opt/<service_name>/<artifact_name> and ARTIFACT_PATH is exported."
  type        = string
}

variable "environment" {
  description = "Environment variables written to /etc/<service_name>.env."
  type        = map(string)
  default     = {}
}

variable "bootstrap_script" {
  description = "Optional root script run after packages and artifact download, before systemd starts the service."
  type        = string
  default     = ""
}

variable "app_log_path" {
  description = "Application log path shipped to CloudWatch; defaults to /var/log/<service_name>/app.log."
  type        = string
  default     = null
}

variable "log_retention_days" {
  description = "CloudWatch application log retention."
  type        = number
  default     = 7
}

variable "root_volume_size" {
  description = "EC2 root gp3 volume size in GiB."
  type        = number
  default     = 16
}

variable "alb_ingress_cidrs" {
  description = "IPv4 CIDRs allowed to reach the ALB listener ports."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "certificate_arn" {
  description = "Optional ACM certificate ARN. When set, HTTPS is served and HTTP redirects to HTTPS."
  type        = string
  default     = null
}

variable "public_hostname" {
  description = "DNS name the caller points at alb_dns_name. Required with certificate_arn and must match the certificate."
  type        = string
  default     = null
}
