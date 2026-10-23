data "aws_vpc" "target" {
  tags = { Name = var.vpc_name }
}

data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.target.id]
  }

  filter {
    name   = "tag:Name"
    values = ["${var.private_subnet_name_prefix}*"]
  }
}

module "rearchitect" {
  source = "./.."

  service_name         = "sample-service"
  run_token            = "ra-20270101-aa"
  expires              = "2027-01-08T00:00:00Z"
  disposition_evidence = "portfolio/assessment-report.csv:2"
  vpc_id               = data.aws_vpc.target.id
  subnet_ids           = data.aws_subnets.private.ids
  contexts = {
    catalog = {
      schema       = "catalog"
      route_prefix = "/api/catalog"
    }
  }
}
