variable "region" {
  type    = string
  default = "us-east-1"
}

variable "vpc_name" {
  type    = string
  default = "otterworks-dev"
}

variable "public_subnet_name_prefix" {
  type    = string
  default = "otterworks-public-"
}

variable "artifact_path" {
  type        = string
  description = "Path to the built service artifact."
}
