# The sql-runner function executes statements and queries against the run
# database from inside the VPC. scripts/billing-to-rds.py invokes it out-of-band
# (aws lambda invoke) for the schema/data load and the RDS-side baseline counts;
# nothing in here opens an inbound path. It shares the db-init security group:
# no ingress, egress to Postgres on the VPC CIDR only.

locals {
  db_sql       = "${local.name}-billing-sql"
  sql_build_in = "${path.module}/.build/sql_runner"
}

resource "aws_iam_role" "db_sql" {
  name               = local.db_sql
  description        = "Execution role of ${local.db_sql}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "db_sql_vpc" {
  role       = aws_iam_role.db_sql.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_cloudwatch_log_group" "db_sql" { # nosemgrep: terraform.aws.security.aws-cloudwatch-log-group-unencrypted.aws-cloudwatch-log-group-unencrypted
  name              = "/aws/lambda/${local.db_sql}"
  retention_in_days = var.log_retention_days
}

# build-lambda.sh fills .build/sql_runner (handler, pg8000, RDS CA bundle) before plan.
data "archive_file" "db_sql" {
  type        = "zip"
  source_dir  = local.sql_build_in
  output_path = "${path.module}/.build/sql_runner.zip"
}

resource "aws_lambda_function" "db_sql" { # nosemgrep: terraform.aws.security.aws-lambda-x-ray-tracing-not-active.aws-lambda-x-ray-tracing-not-active
  function_name    = local.db_sql
  description      = "Runs SQL against database ${local.db_name} on ${var.db_instance_identifier} for scripts/billing-to-rds.py"
  role             = aws_iam_role.db_sql.arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.db_sql.output_path
  source_code_hash = data.archive_file.db_sql.output_base64sha256
  memory_size      = 256
  timeout          = 300
  architectures    = ["x86_64"]

  vpc_config {
    subnet_ids         = data.aws_db_subnet_group.shared.subnet_ids
    security_group_ids = [aws_security_group.db_init.id]
  }

  depends_on = [aws_cloudwatch_log_group.db_sql, aws_iam_role_policy_attachment.db_sql_vpc]
}
