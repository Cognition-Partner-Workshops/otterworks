locals {
  name = "${var.run_token}-billing"

  tags = {
    demo      = "billing-db"
    service   = "legacy-billing"
    run_token = var.run_token
    RunToken  = var.run_token
    Expires   = var.expires
    ManagedBy = "terraform"
  }

  engine_major = split(".", var.engine_version)[0]

  vpc_id              = var.vpc_id != null ? var.vpc_id : data.aws_vpc.this[0].id
  subnet_ids          = var.subnet_ids != null ? var.subnet_ids : data.aws_subnets.private[0].ids
  allowed_cidr_blocks = var.allowed_cidr_blocks != null ? var.allowed_cidr_blocks : [data.aws_vpc.this[0].cidr_block]

  # Billing results depend on the session TimeZone and DateStyle
  # (services/legacy-billing/db/MANAGED_POSTGRES.md, inventory rows 6-7), so
  # both are pinned here instead of relying on the RDS engine defaults.
  db_parameters = {
    "rds.force_ssl"            = "1"
    "ssl_min_protocol_version" = "TLSv1.2"
    "timezone"                 = "UTC"
    "datestyle"                = "ISO, MDY"
  }
}

check "offline_plan_has_literal_network" {
  assert {
    condition     = !var.offline_plan || (var.vpc_id != null && var.subnet_ids != null && var.allowed_cidr_blocks != null)
    error_message = "offline_plan = true needs vpc_id, subnet_ids and allowed_cidr_blocks; the lookups would call AWS."
  }
}

data "aws_vpc" "this" {
  count = var.vpc_id == null || var.allowed_cidr_blocks == null ? 1 : 0

  id   = var.vpc_id
  tags = var.vpc_id == null ? { Name = var.vpc_name } : null
}

data "aws_subnets" "private" {
  count = var.subnet_ids == null ? 1 : 0

  filter {
    name   = "vpc-id"
    values = [local.vpc_id]
  }

  filter {
    name   = "tag:Name"
    values = ["${var.private_subnet_name_prefix}*"]
  }
}

resource "aws_db_parameter_group" "billing" {
  name        = local.name
  family      = "postgres${local.engine_major}"
  description = "legacy-billing ${var.run_token}: TLS only, UTC, ISO DateStyle"

  dynamic "parameter" {
    for_each = local.db_parameters
    content {
      name         = parameter.key
      value        = parameter.value
      apply_method = "immediate"
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_db_subnet_group" "billing" {
  name        = local.name
  description = "Private subnets for legacy-billing ${var.run_token}"
  subnet_ids  = local.subnet_ids
}

resource "aws_security_group" "billing" {
  name        = "${local.name}-db"
  description = "legacy-billing PostgreSQL ${var.run_token}: 5432 from the cluster VPC only"
  vpc_id      = local.vpc_id

  tags = {
    Name = "${local.name}-db"
  }
}

# No egress rule: Terraform drops the default allow-all egress on create, and
# RDS needs none for client connections.
resource "aws_vpc_security_group_ingress_rule" "postgres" {
  for_each = toset(local.allowed_cidr_blocks)

  security_group_id = aws_security_group.billing.id
  description       = "PostgreSQL from ${each.value}"
  cidr_ipv4         = each.value
  from_port         = 5432
  to_port           = 5432
  ip_protocol       = "tcp"
}

# Created here rather than by RDS on first export, so they carry the run tags
# and a retention.
resource "aws_cloudwatch_log_group" "billing" { # nosemgrep: terraform.aws.security.aws-cloudwatch-log-group-unencrypted.aws-cloudwatch-log-group-unencrypted
  for_each = toset(["postgresql", "upgrade"])

  name              = "/aws/rds/instance/${local.name}/${each.key}"
  retention_in_days = var.log_retention_days
}

resource "aws_db_instance" "billing" {
  identifier     = local.name
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true

  # The billing database is created by bootstrap/create-database.sql with an
  # explicit locale; RDS only creates `postgres` here.
  db_name                     = null
  username                    = var.master_username
  manage_master_user_password = true

  parameter_group_name   = aws_db_parameter_group.billing.name
  db_subnet_group_name   = aws_db_subnet_group.billing.name
  vpc_security_group_ids = [aws_security_group.billing.id]
  publicly_accessible    = false
  multi_az               = var.multi_az
  ca_cert_identifier     = "rds-ca-rsa2048-g1"

  # Same minor as the parity runs; upgrades go through a reviewed change.
  auto_minor_version_upgrade  = false
  allow_major_version_upgrade = false

  backup_retention_period   = var.backup_retention_days
  backup_window             = "03:00-04:00"
  maintenance_window        = "sun:04:30-sun:05:30"
  copy_tags_to_snapshot     = true
  delete_automated_backups  = false
  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = false
  final_snapshot_identifier = "${local.name}-final"

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  depends_on = [aws_cloudwatch_log_group.billing]
}
