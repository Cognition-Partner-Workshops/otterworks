# The shared instance is private (no public endpoint, 5432 open to the VPC CIDR only,
# private subnets without NAT or VPC endpoints), so nothing outside the VPC reaches it.
# A short-lived function in the instance's own private subnets runs the DDL instead:
# it opens no inbound path and has no route out of the VPC. Terraform passes the
# credentials in the invocation payload, so the function needs no Secrets Manager endpoint.

resource "random_password" "billing" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "billing_db" { # nosemgrep: terraform.aws.security.aws-secretsmanager-secret-unencrypted.aws-secretsmanager-secret-unencrypted
  name                    = "otterworks-${local.name}/billing-db"
  description             = "Login role ${local.db_role} of database ${local.db_name} on ${var.db_instance_identifier} (billing-data, ${local.name})."
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "billing_db" {
  secret_id = aws_secretsmanager_secret.billing_db.id
  secret_string = jsonencode({
    engine   = "postgres"
    host     = data.aws_db_instance.shared.address
    port     = data.aws_db_instance.shared.port
    dbname   = local.db_name
    username = local.db_role
    password = random_password.billing.result
  })
}

resource "aws_security_group" "db_init" {
  name        = local.db_init
  description = "${local.db_init}: no inbound, egress to Postgres inside the VPC only"
  vpc_id      = data.aws_vpc.shared.id
  tags        = { Name = local.db_init }
}

resource "aws_vpc_security_group_egress_rule" "db_init_postgres" {
  security_group_id = aws_security_group.db_init.id
  description       = "Postgres on the shared instance"
  ip_protocol       = "tcp"
  from_port         = data.aws_db_instance.shared.port
  to_port           = data.aws_db_instance.shared.port
  cidr_ipv4         = data.aws_vpc.shared.cidr_block
}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "db_init" {
  name               = local.db_init
  description        = "Execution role of ${local.db_init}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "db_init_vpc" {
  role       = aws_iam_role.db_init.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

data "aws_partition" "current" {}

resource "aws_cloudwatch_log_group" "db_init" { # nosemgrep: terraform.aws.security.aws-cloudwatch-log-group-unencrypted.aws-cloudwatch-log-group-unencrypted
  name              = "/aws/lambda/${local.db_init}"
  retention_in_days = var.log_retention_days
}

# build-lambda.sh fills .build/db_init (handler, pg8000, RDS CA bundle) before plan.
data "archive_file" "db_init" {
  type        = "zip"
  source_dir  = local.build_in
  output_path = "${path.module}/.build/db_init.zip"
}

resource "aws_lambda_function" "db_init" { # nosemgrep: terraform.aws.security.aws-lambda-x-ray-tracing-not-active.aws-lambda-x-ray-tracing-not-active
  function_name    = local.db_init
  description      = "Creates and drops database ${local.db_name} and role ${local.db_role} on ${var.db_instance_identifier}"
  role             = aws_iam_role.db_init.arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.db_init.output_path
  source_code_hash = data.archive_file.db_init.output_base64sha256
  memory_size      = 256
  timeout          = 120
  architectures    = ["x86_64"]

  vpc_config {
    subnet_ids         = data.aws_db_subnet_group.shared.subnet_ids
    security_group_ids = [aws_security_group.db_init.id]
  }

  depends_on = [aws_cloudwatch_log_group.db_init, aws_iam_role_policy_attachment.db_init_vpc]
}

# CRUD scope: create/update run with tf.action=create|update, destroy runs tf.action=delete
# (DROP DATABASE ... WITH (FORCE), DROP ROLE) before the function itself is removed.
resource "aws_lambda_invocation" "database" {
  function_name   = aws_lambda_function.db_init.function_name
  lifecycle_scope = "CRUD"
  terraform_key   = "tf"

  input = jsonencode({
    master = {
      host     = data.aws_db_instance.shared.address
      port     = data.aws_db_instance.shared.port
      dbname   = var.master_database
      user     = try(local.master.username, data.aws_db_instance.shared.master_username)
      password = local.master.password
    }
    database         = local.db_name
    role             = local.db_role
    role_password    = random_password.billing.result
    connection_limit = var.app_connection_limit
  })

  depends_on = [aws_secretsmanager_secret_version.billing_db]
}
