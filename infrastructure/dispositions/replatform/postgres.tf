resource "random_password" "postgres" {
  count   = var.postgres == null ? 0 : 1
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "postgres" { # nosemgrep: terraform.aws.security.aws-secretsmanager-secret-unencrypted.aws-secretsmanager-secret-unencrypted
  count                   = var.postgres == null ? 0 : 1
  name                    = "${local.name}/${var.service_name}/postgres"
  description             = "Master credential of the ${local.name} PostgreSQL instance for ${var.service_name}."
  recovery_window_in_days = 0
  tags                    = local.tags
}

resource "aws_secretsmanager_secret_version" "postgres" {
  count     = var.postgres == null ? 0 : 1
  secret_id = aws_secretsmanager_secret.postgres[0].id
  secret_string = jsonencode({
    engine   = "postgres"
    host     = aws_db_instance.postgres[0].address
    port     = aws_db_instance.postgres[0].port
    dbname   = var.postgres.database_name
    username = var.postgres.username
    password = random_password.postgres[0].result
  })
}

resource "aws_db_subnet_group" "postgres" {
  count       = var.postgres == null ? 0 : 1
  name        = "${local.name}-pg"
  description = "Private subnets for ${var.service_name} run ${local.name}"
  subnet_ids  = var.subnet_ids
  tags        = local.tags
}

resource "aws_security_group" "postgres" {
  count       = var.postgres == null ? 0 : 1
  name        = "${local.name}-pg"
  description = "PostgreSQL for ${var.service_name} run ${local.name}; workload clients only"
  vpc_id      = var.vpc_id
  tags        = merge(local.tags, { Name = "${local.name}-pg" })
}

resource "aws_vpc_security_group_ingress_rule" "postgres" {
  for_each                     = var.postgres == null ? {} : local.client_rules
  security_group_id            = aws_security_group.postgres[0].id
  description                  = "PostgreSQL from ${each.key}"
  referenced_security_group_id = each.value.security_group_id
  cidr_ipv4                    = each.value.cidr
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  tags                         = local.tags
}

resource "aws_db_instance" "postgres" { # nosemgrep: terraform.aws.security.aws-rds-backup-no-retention.aws-rds-backup-no-retention
  count                           = var.postgres == null ? 0 : 1
  identifier                      = "${local.name}-pg"
  engine                          = "postgres"
  engine_version                  = var.postgres.engine_version
  instance_class                  = var.postgres.instance_class
  allocated_storage               = var.postgres.allocated_storage
  max_allocated_storage           = var.postgres.max_allocated_storage
  storage_type                    = "gp3"
  storage_encrypted               = true
  db_name                         = var.postgres.database_name
  username                        = var.postgres.username
  password                        = random_password.postgres[0].result
  db_subnet_group_name            = aws_db_subnet_group.postgres[0].name
  vpc_security_group_ids          = [aws_security_group.postgres[0].id]
  publicly_accessible             = false
  multi_az                        = var.postgres.multi_az
  backup_retention_period         = var.postgres.backup_retention_days
  deletion_protection             = var.postgres.deletion_protection
  skip_final_snapshot             = var.postgres.skip_final_snapshot
  final_snapshot_identifier       = var.postgres.skip_final_snapshot ? null : "${local.name}-pg-final"
  copy_tags_to_snapshot           = true
  auto_minor_version_upgrade      = true
  allow_major_version_upgrade     = false
  apply_immediately               = true
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  tags                            = local.tags

  depends_on = [terraform_data.inputs]
}
