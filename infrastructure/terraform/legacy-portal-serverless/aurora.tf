resource "random_password" "db" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "db" { # nosemgrep: terraform.aws.security.aws-secretsmanager-secret-unencrypted.aws-secretsmanager-secret-unencrypted
  name                    = "${local.name}/aurora/master"
  description             = "Master credential of the ${local.name} Aurora cluster (legacy-portal-serverless)."
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    username = "legacyportal"
    password = random_password.db.result
    engine   = "postgres"
    dbname   = "legacyportal"
  })
}

resource "aws_db_subnet_group" "this" {
  name        = local.name
  description = "Private subnets of ${var.vpc_name} for ${local.name}"
  subnet_ids  = data.aws_subnets.private.ids
}

# No ingress: the functions reach the cluster through the RDS Data API, so nothing connects on 5432.
resource "aws_security_group" "aurora" {
  name        = "${local.name}-aurora"
  description = "Aurora cluster of ${local.name}; Data API only, no inbound rules"
  vpc_id      = data.aws_vpc.this.id
}

resource "aws_rds_cluster" "this" {
  cluster_identifier          = local.name
  engine                      = "aurora-postgresql"
  engine_mode                 = "provisioned"
  engine_version              = var.aurora_engine_version
  database_name               = "legacyportal"
  master_username             = "legacyportal"
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
}

# Creates the three schemas and their tables through the Data API once the writer is available.
resource "terraform_data" "schema" {
  triggers_replace = [aws_rds_cluster.this.cluster_resource_id, filesha256("${path.module}/schema.sql")]

  provisioner "local-exec" {
    command = "${path.module}/apply-schema.sh"
    environment = {
      CLUSTER_ARN = aws_rds_cluster.this.arn
      SECRET_ARN  = aws_secretsmanager_secret.db.arn
      DATABASE    = aws_rds_cluster.this.database_name
      SQL_FILE    = "${path.module}/schema.sql"
      AWS_REGION  = var.region
    }
  }

  depends_on = [aws_rds_cluster_instance.writer, aws_secretsmanager_secret_version.db]
}
