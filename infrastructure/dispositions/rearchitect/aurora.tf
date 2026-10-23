resource "random_password" "db" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "db" { # nosemgrep: terraform.aws.security.aws-secretsmanager-secret-unencrypted.aws-secretsmanager-secret-unencrypted
  name                    = "${local.name}/aurora/master"
  description             = "Master credential of the ${local.name} Aurora cluster."
  recovery_window_in_days = 0
  tags                    = local.tags
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    username = var.master_username
    password = random_password.db.result
    engine   = "postgres"
    dbname   = var.database_name
  })
}

resource "aws_db_subnet_group" "this" {
  name        = local.name
  description = "Private subnets for ${var.service_name} run ${local.name}"
  subnet_ids  = var.subnet_ids
  tags        = local.tags
}

resource "aws_security_group" "aurora" {
  name        = "${local.name}-aurora"
  description = "Aurora Data API only; no inbound rules"
  vpc_id      = var.vpc_id
  tags        = merge(local.tags, { Name = "${local.name}-aurora" })
}

resource "aws_rds_cluster" "this" {
  cluster_identifier          = local.name
  engine                      = "aurora-postgresql"
  engine_mode                 = "provisioned"
  engine_version              = var.aurora_engine_version
  database_name               = var.database_name
  master_username             = var.master_username
  master_password             = random_password.db.result
  db_subnet_group_name        = aws_db_subnet_group.this.name
  vpc_security_group_ids      = [aws_security_group.aurora.id]
  enable_http_endpoint        = true
  storage_encrypted           = true
  skip_final_snapshot         = true
  deletion_protection         = false
  backup_retention_period     = 1
  copy_tags_to_snapshot       = true
  apply_immediately           = true
  allow_major_version_upgrade = false
  tags                        = local.tags

  serverlessv2_scaling_configuration {
    min_capacity             = var.aurora_min_acu
    max_capacity             = var.aurora_max_acu
    seconds_until_auto_pause = var.aurora_min_acu == 0 ? var.aurora_seconds_until_auto_pause : null
  }
}

resource "aws_rds_cluster_instance" "writer" {
  identifier           = "${local.name}-writer"
  cluster_identifier   = aws_rds_cluster.this.id
  instance_class       = "db.serverless"
  engine               = aws_rds_cluster.this.engine
  engine_version       = aws_rds_cluster.this.engine_version
  db_subnet_group_name = aws_db_subnet_group.this.name
  publicly_accessible  = false
  apply_immediately    = true
  tags                 = local.tags
}

resource "terraform_data" "schema" {
  count = var.schema_sql_path == null ? 0 : 1

  triggers_replace = [
    aws_rds_cluster.this.cluster_resource_id,
    filesha256(abspath(var.schema_sql_path)),
  ]

  provisioner "local-exec" {
    command = "bash ${path.module}/apply-schema.sh"
    environment = {
      CLUSTER_ARN = aws_rds_cluster.this.arn
      SECRET_ARN  = aws_secretsmanager_secret.db.arn
      DATABASE    = aws_rds_cluster.this.database_name
      SQL_FILE    = abspath(var.schema_sql_path)
      AWS_REGION  = data.aws_region.current.name
    }
  }

  depends_on = [aws_rds_cluster_instance.writer, aws_secretsmanager_secret_version.db]
}
