resource "aws_db_parameter_group" "this" {
  name   = "${local.name}-pg16"
  family = "postgres16"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  parameter {
    name  = "ssl_min_protocol_version"
    value = "TLSv1.2"
  }

  # Routines cast timestamptz to date; see services/legacy-billing/db/MANAGED_POSTGRES.md.
  parameter {
    name  = "TimeZone"
    value = "UTC"
  }
}

resource "aws_cloudwatch_log_group" "rds" {
  for_each = toset(local.log_exports)

  name              = "/aws/rds/instance/${local.name}/${each.key}"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.this.arn
}

resource "aws_db_instance" "this" {
  identifier                      = local.name
  engine                          = "postgres"
  engine_version                  = var.engine_version
  instance_class                  = var.instance_class
  storage_type                    = "gp3"
  allocated_storage               = var.allocated_storage
  max_allocated_storage           = var.max_allocated_storage
  storage_encrypted               = true
  kms_key_id                      = aws_kms_key.this.arn
  db_name                         = var.db_name
  username                        = var.master_username
  manage_master_user_password     = true
  master_user_secret_kms_key_id   = aws_kms_key.this.key_id
  port                            = local.port
  parameter_group_name            = aws_db_parameter_group.this.name
  db_subnet_group_name            = aws_db_subnet_group.this.name
  vpc_security_group_ids          = [aws_security_group.db.id]
  publicly_accessible             = false
  multi_az                        = var.multi_az
  ca_cert_identifier              = "rds-ca-rsa2048-g1"
  backup_retention_period         = var.backup_retention_days
  backup_window                   = "03:00-04:00"
  maintenance_window              = "sun:04:30-sun:05:30"
  copy_tags_to_snapshot           = true
  deletion_protection             = var.deletion_protection
  skip_final_snapshot             = false
  final_snapshot_identifier       = "${local.name}-final"
  auto_minor_version_upgrade      = true
  allow_major_version_upgrade     = false
  apply_immediately               = false
  enabled_cloudwatch_logs_exports = local.log_exports

  depends_on = [aws_cloudwatch_log_group.rds]
}
