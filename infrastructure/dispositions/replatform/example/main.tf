data "aws_eks_cluster" "target" {
  name = var.cluster_name
}

data "aws_iam_openid_connect_provider" "target" {
  url = data.aws_eks_cluster.target.identity[0].oidc[0].issuer
}

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

module "replatform" {
  source = "./.."

  service_name              = "sample-service"
  run_token                 = "replat-20270101-aa"
  expires                   = "2027-01-08T00:00:00Z"
  disposition_evidence      = "portfolio/assessment-report.csv:2"
  vpc_id                    = data.aws_vpc.target.id
  subnet_ids                = data.aws_subnets.private.ids
  client_security_group_ids = [data.aws_eks_cluster.target.vpc_config[0].cluster_security_group_id]
  oidc_provider_arn         = data.aws_iam_openid_connect_provider.target.arn
  namespace                 = var.namespace
  image_repository          = var.image_repository
  image_tag                 = var.image_tag

  postgres = {}
  buckets  = { files = {} }
}
