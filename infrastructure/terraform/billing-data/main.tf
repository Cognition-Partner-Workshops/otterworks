locals {
  name = var.run_token

  # Postgres identifiers cannot contain '-': lp-20261006-bd -> lp_20261006_bd.
  db_name  = replace(var.run_token, "-", "_")
  db_role  = "${local.db_name}_billing"
  db_init  = "${local.name}-billing-db-init"
  build_in = "${path.module}/.build/db_init"

  tags = {
    demo      = "billing-off-legacy"
    run_token = var.run_token
    Expires   = var.expires
    ManagedBy = "terraform"
    Project   = "otterworks"
  }
}

data "aws_db_instance" "shared" {
  db_instance_identifier = var.db_instance_identifier
}

data "aws_db_subnet_group" "shared" {
  name = data.aws_db_instance.shared.db_subnet_group
}

data "aws_vpc" "shared" {
  id = data.aws_db_subnet_group.shared.vpc_id
}

data "aws_secretsmanager_secret_version" "master" {
  secret_id = var.master_secret_id
}

locals {
  master = jsondecode(data.aws_secretsmanager_secret_version.master.secret_string)
}
