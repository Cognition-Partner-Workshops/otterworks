resource "aws_db_subnet_group" "this" {
  name        = local.name
  description = "Private subnets of ${var.vpc_name} for ${local.name}"
  subnet_ids  = data.aws_subnets.private.ids
}

resource "aws_security_group" "db" {
  name        = "${local.name}-db"
  description = "PostgreSQL database for ${local.name}"
  vpc_id      = data.aws_vpc.this.id
  egress      = []
}

resource "aws_security_group" "client" {
  name        = "${local.name}-client"
  description = "Client access for legacy-billing pods and migration job"
  vpc_id      = data.aws_vpc.this.id
  egress      = []
}

resource "aws_vpc_security_group_ingress_rule" "db_from_client" {
  security_group_id            = aws_security_group.db.id
  description                  = "PostgreSQL from the legacy-billing client security group"
  ip_protocol                  = "tcp"
  from_port                    = local.port
  to_port                      = local.port
  referenced_security_group_id = aws_security_group.client.id
}

resource "aws_vpc_security_group_egress_rule" "client_to_db" {
  security_group_id            = aws_security_group.client.id
  description                  = "PostgreSQL to the legacy-billing database security group"
  ip_protocol                  = "tcp"
  from_port                    = local.port
  to_port                      = local.port
  referenced_security_group_id = aws_security_group.db.id
}
