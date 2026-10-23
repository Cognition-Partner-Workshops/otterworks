module "replatform" {
  source = "./.."

  service_name              = "sample-service"
  run_token                 = var.run_token
  expires                   = var.expires
  disposition_evidence      = "portfolio/assessment-report.csv:2"
  vpc_id                    = "vpc-0123456789abcdef0"
  subnet_ids                = ["subnet-0123456789abcdef0", "subnet-0123456789abcdef1"]
  client_security_group_ids = ["sg-0123456789abcdef0"]
  oidc_provider_arn         = "arn:aws:iam::123456789012:oidc-provider/oidc.eks.us-east-1.amazonaws.com/id/EXAMPLED539D4633E53DE1B71EXAMPLE"
  namespace                 = "otterworks-ci"
  image_repository          = "123456789012.dkr.ecr.us-east-1.amazonaws.com/sample-service"
  image_tag                 = "ci"
  ingress_host              = "sample.example.invalid"
  environment               = { FEATURE_MODE = "ci" }
  upgrade_paths             = { java = "Java 8 -> 21 (modernization-target-standard)" }

  postgres = {}
  redis    = {}
  buckets = {
    files = { versioning = true }
  }
  queues = {
    events = {}
  }
}
