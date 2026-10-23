variable "region" {
  type    = string
  default = "us-east-1"
}

variable "vpc_name" {
  type    = string
  default = "otterworks-dev"
}

variable "private_subnet_name_prefix" {
  type    = string
  default = "otterworks-private-"
}
