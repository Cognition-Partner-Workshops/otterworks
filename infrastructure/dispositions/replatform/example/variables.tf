variable "region" {
  type    = string
  default = "us-east-1"
}

variable "cluster_name" {
  type    = string
  default = "otterworks-dev"
}

variable "vpc_name" {
  type    = string
  default = "otterworks-dev"
}

variable "private_subnet_name_prefix" {
  type    = string
  default = "otterworks-private-"
}

variable "namespace" {
  type        = string
  description = "Tenant namespace otterworks-<ID>; never otterworks-main."
}

variable "image_repository" {
  type        = string
  description = "ECR repository of the service image, e.g. <account>.dkr.ecr.us-east-1.amazonaws.com/<service>."
}

variable "image_tag" {
  type = string
}
