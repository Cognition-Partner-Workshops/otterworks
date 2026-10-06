# ------------------------------------------------------------------------------
# Reliability sandbox for the messaging module
#
# Instantiates the production module ../modules/messaging under new, run-token
# names with its own local state, plus a DynamoDB ledger that stands in for the
# analytics consumer's durable write. Nothing here reads or changes shared
# state, tenants, the EKS cluster or any existing queue, topic or role.
# Drive it with scripts/sandbox-messaging.sh.
# ------------------------------------------------------------------------------

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      run_token = var.run_token
      Expires   = var.expires
      Project   = "otterworks-reliability-sandbox"
      ManagedBy = "terraform"
      Layer     = "sandbox"
    }
  }
}

module "messaging" {
  source = "../modules/messaging"

  project           = var.run_token
  environment       = "dev"
  max_receive_count = var.max_receive_count

  # Alarms change state visibly but never page a responder from the sandbox.
  alarm_actions = []
}

# One item per business event plus a ROLLUP#analytics counter; the drill proves
# each event is applied exactly once across failures, redrive and redelivery.
resource "aws_dynamodb_table" "ledger" {
  name         = "${var.run_token}-analytics-ledger"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"

  attribute {
    name = "pk"
    type = "S"
  }
}

# Injected dependency outage for the drill: until ledger_outage_until every
# write to this token's ledger is denied by DynamoDB itself, so the consumer
# fails for real and SQS dead-letters the events. Re-applying with the default
# ends the outage; the policy never covers anything but this table.
resource "aws_dynamodb_resource_policy" "ledger_outage" {
  resource_arn = aws_dynamodb_table.ledger.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "SandboxLedgerOutage"
      Effect    = "Deny"
      Principal = "*"
      Action    = ["dynamodb:PutItem", "dynamodb:UpdateItem"]
      Resource  = aws_dynamodb_table.ledger.arn
      Condition = { DateLessThan = { "aws:CurrentTime" = var.ledger_outage_until } }
    }]
  })
}
