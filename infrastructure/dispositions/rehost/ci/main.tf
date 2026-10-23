module "rehost" {
  source = "./.."

  service_name         = "sample-service"
  run_token            = var.run_token
  expires              = var.expires
  disposition_evidence = "portfolio/assessment-report.csv:2"
  vpc_id               = "vpc-0123456789abcdef0"
  subnet_ids           = ["subnet-0123456789abcdef0", "subnet-0123456789abcdef1"]
  ami_id               = "ami-0123456789abcdef0"
  artifact_path        = var.artifact_path
  artifact_name        = "service-package.bin"
  packages             = ["java-17-amazon-corretto-headless"]
  start_command        = "/opt/sample-service/service-package.bin"
  environment          = { APP_MODE = "test", TRACE_LEVEL = "info" }
  certificate_arn      = "arn:aws:acm:us-east-1:123456789012:certificate/00000000-0000-0000-0000-000000000000"
}
