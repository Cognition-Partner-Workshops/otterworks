module "rearchitect" {
  source = "./.."

  service_name         = "sample-service"
  run_token            = var.run_token
  expires              = var.expires
  disposition_evidence = "portfolio/assessment-report.csv:2"
  vpc_id               = "vpc-0123456789abcdef0"
  subnet_ids           = ["subnet-0123456789abcdef0", "subnet-0123456789abcdef1"]
  account_id           = "123456789012"
  builder_role_name    = "devin-cw-builder"
  schema_sql_path      = "${path.root}/schema.sql"
  devin_webhook_url    = "https://example.invalid/automation"
  devin_webhook_secret = "ci-not-a-secret"
  contexts = {
    catalog = {
      schema           = "catalog"
      route_prefix     = "/api/catalog"
      publishes_events = true
      environment      = { FEATURE_MODE = "ci" }
    }
    profile = {
      schema       = "profile"
      route_prefix = "/api/profile"
    }
  }
  event_subscriptions = {
    catalog-events = {
      source       = "sample-service.catalog"
      detail_types = ["record.created", "record.updated"]
    }
  }
  probe_steps = [
    { name = "GET catalog", path = "/api/catalog" }
  ]
}
