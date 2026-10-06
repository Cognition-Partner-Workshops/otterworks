variable "run_token" {
  description = "Run token, lp-ec2-<yyyymmdd>-<two characters>. Used in every resource name and in the run_token tag."
  type        = string

  validation {
    condition     = can(regex("^lp-ec2-[0-9]{8}-[a-z0-9]{2}$", var.run_token))
    error_message = "run_token must look like lp-ec2-20261006-b1."
  }
}

variable "expires" {
  description = "Expiry date written to the Expires tag, set by lp-ec2-up at apply time."
  type        = string
  default     = "unset"
}

variable "region" {
  description = "AWS region of the otterworks-dev VPC."
  type        = string
  default     = "us-east-1"
}

variable "vpc_name" {
  description = "Name tag of the existing VPC whose public subnets carry the instance and the load balancer."
  type        = string
  default     = "otterworks-dev"
}

variable "public_subnet_name_prefix" {
  description = "Name tag prefix of the existing public subnets."
  type        = string
  default     = "otterworks-public-"
}

variable "instance_type" {
  description = "EC2 instance type for the monolith host."
  type        = string
  default     = "t3.small"
}

variable "app_port" {
  description = "Port the legacy-portal Spring Boot process listens on."
  type        = number
  default     = 8095
}

variable "jar_path" {
  description = "Fat jar uploaded to the run's artifact bucket. lp-ec2-up builds it with ./mvnw -q -DskipTests package before planning."
  type        = string
  default     = "../../../services/legacy-portal/target/legacy-portal.jar"
}

variable "log_retention_days" {
  description = "Retention for the application log group."
  type        = number
  default     = 7
}
