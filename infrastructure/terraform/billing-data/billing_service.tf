# billing-service itself, unchanged, packaged as a function in the instance's
# private subnets so it can reach the run database. Nothing here opens an
# inbound path: no function URL, no API Gateway, no ingress rule. The operator
# reaches it with scripts/billing-service-proxy.py, which turns local HTTP into
# lambda:Invoke calls and passes the run's login credentials in the payload.
# It shares the db-init security group: no ingress, egress to Postgres on the
# VPC CIDR only.

locals {
  billing_service  = "${local.name}-billing-service"
  service_build_in = "${path.module}/.build/billing_service"
}

resource "aws_iam_role" "billing_service" {
  name               = local.billing_service
  description        = "Execution role of ${local.billing_service}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "billing_service_vpc" {
  role       = aws_iam_role.billing_service.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_cloudwatch_log_group" "billing_service" { # nosemgrep: terraform.aws.security.aws-cloudwatch-log-group-unencrypted.aws-cloudwatch-log-group-unencrypted
  name              = "/aws/lambda/${local.billing_service}"
  retention_in_days = var.log_retention_days
}

# build-lambda.sh fills .build/billing_service (services/billing-service app and
# db, its runtime wheels for python3.12/x86_64, Mangum, RDS CA bundle) before plan.
data "archive_file" "billing_service" {
  type        = "zip"
  source_dir  = local.service_build_in
  output_path = "${path.module}/.build/billing_service.zip"
}

resource "aws_lambda_function" "billing_service" { # nosemgrep: terraform.aws.security.aws-lambda-x-ray-tracing-not-active.aws-lambda-x-ray-tracing-not-active
  function_name    = local.billing_service
  description      = "services/billing-service on database ${local.db_name} of ${var.db_instance_identifier}; invoke only, via scripts/billing-service-proxy.py"
  role             = aws_iam_role.billing_service.arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.billing_service.output_path
  source_code_hash = data.archive_file.billing_service.output_base64sha256
  memory_size      = 512
  timeout          = 60
  architectures    = ["x86_64"]

  environment { # nosemgrep: terraform.aws.security.aws-lambda-environment-unencrypted.aws-lambda-environment-unencrypted
    variables = {
      BILLING_SVC_ALLOW_INTERNAL_RESET = "false"
    }
  }

  vpc_config {
    subnet_ids         = data.aws_db_subnet_group.shared.subnet_ids
    security_group_ids = [aws_security_group.db_init.id]
  }

  depends_on = [aws_cloudwatch_log_group.billing_service, aws_iam_role_policy_attachment.billing_service_vpc]
}
