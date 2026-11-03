variable "region" {
  type    = string
  default = "us-east-1"
}

variable "name" {
  type    = string
  default = "ow-tp-oracle-billing"
}

variable "instance_type" {
  description = "Oracle Free plus the demo-scale seed fits in 8 GiB."
  type        = string
  default     = "t3.large"
}

variable "root_volume_gb" {
  type    = number
  default = 40
}

variable "oracle_cidrs" {
  description = "Who may reach 1521. Defaults to the Devin session egress range."
  type        = list(string)
  default     = ["140.232.64.0/24"]
}

variable "ssh_cidrs" {
  description = "Optional SSH access. Leave empty and use SSM Session Manager instead."
  type        = list(string)
  default     = []
}

variable "key_name" {
  type    = string
  default = null
}

variable "repo_url" {
  type    = string
  default = "https://github.com/Cognition-Partner-Workshops/otterworks.git"
}

variable "repo_ref" {
  type    = string
  default = "tech-partnerships"
}

variable "seed_ns" {
  type    = string
  default = "demo"
}

variable "seed_scale" {
  type    = string
  default = "demo"
}

variable "ro_user" {
  description = "Read-only login the migration doctor and recon jobs use."
  type        = string
  default     = "ow_billing_ro"
}

variable "ro_password" {
  description = "Password for ro_user. Pass with TF_VAR_ro_password; stored as an SSM SecureString."
  type        = string
  sensitive   = true
}
