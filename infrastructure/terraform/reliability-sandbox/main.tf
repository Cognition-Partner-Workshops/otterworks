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
