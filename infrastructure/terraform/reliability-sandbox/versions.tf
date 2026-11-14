terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
  }

  # Local state only, one file per run token, kept outside the repository:
  # scripts/sandbox-messaging.sh passes -backend-config=path=... at init.
  backend "local" {}
}
