variable "service_name" {
  description = "Lowercase identifier of the application being replatformed. Names the Helm release and Kubernetes objects."
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
    error_message = "run_token must match <prefix>-YYYYMMDD-xx and be at most 28 characters so RDS, ElastiCache, IAM and S3 names fit AWS limits."
  }
}

variable "expires" {
  description = "RFC 3339 expiry timestamp applied to the Expires tag and the otterworks.io/expires annotation."
  type        = string

  validation {
    condition     = can(formatdate("YYYY", var.expires))
    error_message = "expires must be a valid RFC 3339 timestamp."
  }
}

variable "disposition_evidence" {
  description = "Assessment-report row pointer stamped as an AWS tag value; do not pass the evidence list."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9 _.:/=+@-]{1,256}$", var.disposition_evidence))
    error_message = "disposition_evidence becomes a tag value: at most 256 characters from letters, digits, spaces and _ . : / = + - @. Point at the assessment row, e.g. portfolio/assessment-report.csv:3, not the evidence list itself."
  }
}

variable "extra_tags" {
  description = "Additional AWS tags with values up to 256 characters using letters, digits, spaces and _ . : / = + - @; mandatory disposition tags take precedence."
  type        = map(string)
  default     = {}

  validation {
    condition     = alltrue([for v in values(var.extra_tags) : can(regex("^[A-Za-z0-9 _.:/=+@-]{1,256}$", v))])
    error_message = "extra_tags values must contain at most 256 characters from letters, digits, spaces and _ . : / = + - @."
  }
}

variable "vpc_id" {
  description = "Existing VPC of the EKS cluster. Required when postgres or redis is set."
  type        = string
  default     = null
}

variable "subnet_ids" {
  description = "Existing private subnet IDs in at least two availability zones for the database and cache subnet groups."
  type        = list(string)
  default     = []
}

variable "client_security_group_ids" {
  description = "Security groups allowed to reach the database and cache, normally the EKS cluster or node security group."
  type        = list(string)
  default     = []
}

variable "client_cidr_blocks" {
  description = "CIDR blocks allowed to reach the database and cache, as an alternative to client_security_group_ids."
  type        = list(string)
  default     = []
}

variable "postgres" {
  description = "Managed PostgreSQL (RDS) for the application's relational store. null creates no database."
  type = object({
    engine_version        = optional(string, "16")
    instance_class        = optional(string, "db.t4g.micro")
    allocated_storage     = optional(number, 20)
    max_allocated_storage = optional(number, 50)
    database_name         = optional(string, "app")
    username              = optional(string, "app_admin")
    backup_retention_days = optional(number, 1)
    multi_az              = optional(bool, false)
    deletion_protection   = optional(bool, false)
    skip_final_snapshot   = optional(bool, true)
  })
  default = null

  validation {
    condition     = var.postgres == null || can(regex("^[a-zA-Z][a-zA-Z0-9_]{0,62}$", var.postgres.database_name))
    error_message = "postgres.database_name must start with a letter and contain only letters, digits, or underscores."
  }
}

variable "redis" {
  description = "Managed Redis (ElastiCache) for cache or session state. null creates no cache."
  type = object({
    engine_version     = optional(string, "7.1")
    node_type          = optional(string, "cache.t4g.micro")
    num_cache_clusters = optional(number, 1)
  })
  default = null

  validation {
    condition     = var.redis == null || try(var.redis.num_cache_clusters >= 1 && var.redis.num_cache_clusters <= 6, false)
    error_message = "redis.num_cache_clusters must be between 1 and 6."
  }
}

variable "buckets" {
  description = "Managed S3 buckets for file storage, keyed by a short name. Each is private, encrypted and readable/writable by the service account."
  type = map(object({
    versioning    = optional(bool, false)
    force_destroy = optional(bool, true)
  }))
  default = {}

  validation {
    condition     = alltrue([for key, _ in var.buckets : can(regex("^[a-z0-9][a-z0-9-]{0,19}$", key))])
    error_message = "bucket keys must be 1 to 20 lowercase letters, digits, or hyphens."
  }
}

variable "queues" {
  description = "Managed SQS queues, keyed by a short name. Each gets a dead-letter queue and send/receive access for the service account."
  type = map(object({
    fifo                       = optional(bool, false)
    visibility_timeout_seconds = optional(number, 30)
    message_retention_seconds  = optional(number, 345600)
    max_receive_count          = optional(number, 5)
  }))
  default = {}

  validation {
    condition     = alltrue([for key, _ in var.queues : can(regex("^[a-z0-9][a-z0-9-]{0,29}$", key))])
    error_message = "queue keys must be 1 to 30 lowercase letters, digits, or hyphens."
  }
}

variable "upgrade_paths" {
  description = "Named upgrade path for each component past end of life, e.g. { java = \"Java 8 -> 21\" }. Stamped on the release as evidence."
  type        = map(string)
  default     = {}
}

variable "oidc_provider_arn" {
  description = "IAM OIDC provider ARN of the EKS cluster. When set, an IRSA role is created for the service account."
  type        = string
  default     = null
}

variable "namespace" {
  description = "Kubernetes namespace of the release, e.g. otterworks-<tenant>. Never the t-main namespace."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", var.namespace)) && var.namespace != "otterworks-main"
    error_message = "namespace must be a valid Kubernetes namespace name and must not be otterworks-main."
  }
}

variable "service_account_name" {
  description = "Kubernetes service account name. null uses service_name."
  type        = string
  default     = null
}

variable "iam_policy_statements" {
  description = "Extra IAM statements for the service account role, for AWS calls the module does not cover."
  type = list(object({
    sid       = optional(string)
    actions   = list(string)
    resources = list(string)
  }))
  default = []
}

variable "deploy_release" {
  description = "Install the bundled chart with helm_release. false provisions only the managed services and the IRSA role."
  type        = bool
  default     = true
}

variable "image_repository" {
  description = "Container image repository. Required when deploy_release is true."
  type        = string
  default     = ""
}

variable "image_tag" {
  description = "Container image tag. Required when deploy_release is true."
  type        = string
  default     = ""
}

variable "container_port" {
  description = "Port the container listens on."
  type        = number
  default     = 8080
}

variable "health_check_path" {
  description = "HTTP path for liveness and readiness probes."
  type        = string
  default     = "/health"
}

variable "replicas" {
  description = "Deployment replica count."
  type        = number
  default     = 1
}

variable "environment" {
  description = "Non-secret environment settings passed to the chart's ConfigMap. Module-provided connection keys win on conflict."
  type        = map(string)
  default     = {}
}

variable "ingress_host" {
  description = "Host routed through the shared ingress-nginx. null leaves the service cluster-internal."
  type        = string
  default     = null
}

variable "chart_values" {
  description = "Extra YAML documents merged after the module's values, for chart settings the module does not expose."
  type        = list(string)
  default     = []
}

variable "helm_timeout_seconds" {
  description = "Seconds helm waits for the release to become ready."
  type        = number
  default     = 300
}
