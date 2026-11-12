variable "run_token" {
  description = "Run token, lp-<ann|pref|fb>-<yyyymmdd>-<two characters>, the abbreviation naming the module. Used in every resource name and in the run_token tag."
  type        = string

  validation {
    condition     = can(regex("^lp-(ann|pref|fb)-[0-9]{8}-[a-z0-9]{2}$", var.run_token))
    error_message = "run_token must look like lp-ann-20261006-a1, lp-pref-20261006-a1 or lp-fb-20261006-a1."
  }
}

variable "module" {
  description = "Bounded context moved to Lambda: announcements, preferences or feedback. Its code is services/legacy-portal-lambda/<module>."
  type        = string

  validation {
    condition     = contains(["announcements", "preferences", "feedback"], var.module)
    error_message = "module must be announcements, preferences or feedback."
  }
}

variable "ec2_run_token" {
  description = "Run token of the legacy-portal-ec2 stack that keeps serving every route outside the module's prefix. Its ALB is named after it."
  type        = string

  validation {
    condition     = can(regex("^lp-ec2-[0-9]{8}-[a-z0-9]{2}$", var.ec2_run_token))
    error_message = "ec2_run_token must look like lp-ec2-20261006-b1."
  }
}

variable "expires" {
  description = "Expiry date written to the Expires tag, set by lp-mod-up at apply time."
  type        = string
  default     = "unset"
}

variable "region" {
  description = "AWS region of the otterworks-dev VPC."
  type        = string
  default     = "us-east-1"
}

variable "vpc_name" {
  description = "Name tag of the existing VPC whose private subnets carry the Aurora cluster."
  type        = string
  default     = "otterworks-dev"
}

variable "private_subnet_name_prefix" {
  description = "Name tag prefix of the existing private subnets."
  type        = string
  default     = "otterworks-private-"
}

variable "jar_path" {
  description = "Shaded jar of services/legacy-portal-lambda/<module>. lp-mod-up builds it with mvn package and passes its path."
  type        = string
}

variable "event_source" {
  description = "Source the announcements rule matches. Must equal EventBridgeAnnouncementEvents.SOURCE in services/legacy-portal-lambda/announcements."
  type        = string
  default     = "otterworks.legacy-portal"
}

variable "aurora_engine_version" {
  description = "Aurora PostgreSQL engine version. 16.3 or later supports a 0 ACU floor."
  type        = string
  default     = "16.13"
}

variable "aurora_min_acu" {
  description = "Aurora Serverless v2 minimum capacity in ACUs. 0 lets the cluster pause when idle."
  type        = number
  default     = 0
}

variable "aurora_max_acu" {
  description = "Aurora Serverless v2 maximum capacity in ACUs."
  type        = number
  default     = 1
}

variable "aurora_seconds_until_auto_pause" {
  description = "Idle seconds before a 0 ACU cluster pauses."
  type        = number
  default     = 3600
}

variable "lambda_memory_mb" {
  description = "Memory of the module's function."
  type        = number
  default     = 1024
}

variable "log_retention_days" {
  description = "Retention of the Lambda, API access and event log groups."
  type        = number
  default     = 3
}
