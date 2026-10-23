data "aws_vpc" "target" {
  tags = { Name = var.vpc_name }
}

data "aws_subnets" "public" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.target.id]
  }

  filter {
    name   = "tag:Name"
    values = ["${var.public_subnet_name_prefix}*"]
  }
}

module "rehost" {
  source = "./.."

  service_name         = "sample-service"
  run_token            = "rehost-20270101-aa"
  expires              = "2027-01-08T00:00:00Z"
  disposition_evidence = "portfolio/assessment-report.csv:2"
  vpc_id               = data.aws_vpc.target.id
  subnet_ids           = data.aws_subnets.public.ids
  artifact_path        = var.artifact_path
  start_command        = "java -jar /opt/sample-service/app.jar"
  artifact_name        = "app.jar"
  packages             = ["java-17-amazon-corretto-headless"]
}
