# ------------------------------------------------------------------------------
# OtterWorks OpenSearch Serverless Module (namespaced)
#
# Provisions an Amazon OpenSearch Serverless SEARCH collection plus the three
# required security policies (encryption, network, data access) as the managed,
# serverless target for the search-service migration.
#
# Everything is namespaced with `var.namespace_suffix` (default "os-demo") so
# this module lives ALONGSIDE the self-managed MeiliSearch `search` module and
# concurrent migration runs never collide. The whole target is reversible with:
#   terraform destroy -target=module.opensearch
# ------------------------------------------------------------------------------

locals {
  ns = var.namespace_suffix
  common_tags = {
    Module    = "opensearch"
    Project   = var.project
    Namespace = local.ns
  }

  # AOSS resource names must be lowercase, 3-32 chars, [a-z0-9-].
  collection_name = "${var.project}-${local.ns}"
  enc_policy_name = "${var.project}-${local.ns}-enc"
  net_policy_name = "${var.project}-${local.ns}-net"
  acc_policy_name = "${var.project}-${local.ns}-data"
}

# --- Encryption policy (required before the collection can be created) ---

resource "aws_opensearchserverless_security_policy" "encryption" {
  name = local.enc_policy_name
  type = "encryption"

  policy = jsonencode({
    Rules = [
      {
        ResourceType = "collection"
        Resource     = ["collection/${local.collection_name}"]
      }
    ]
    AWSOwnedKey = true
  })
}

# --- Network policy (collection endpoint + Dashboards access) ---

resource "aws_opensearchserverless_security_policy" "network" {
  name = local.net_policy_name
  type = "network"

  policy = jsonencode([
    {
      Description = "Access for OtterWorks search-service (${local.ns})"
      Rules = [
        {
          ResourceType = "collection"
          Resource     = ["collection/${local.collection_name}"]
        },
        {
          ResourceType = "dashboard"
          Resource     = ["collection/${local.collection_name}"]
        }
      ]
      AllowFromPublic = var.allow_public_access
    }
  ])
}

# --- Data access policy (data-plane permissions, least privilege) ---

resource "aws_opensearchserverless_access_policy" "data" {
  count = length(var.data_access_principal_arns) > 0 ? 1 : 0

  name = local.acc_policy_name
  type = "data"

  policy = jsonencode([
    {
      Description = "search-service data access (${local.ns})"
      Rules = [
        {
          ResourceType = "index"
          Resource     = ["index/${local.collection_name}/*"]
          Permission = [
            "aoss:CreateIndex",
            "aoss:DeleteIndex",
            "aoss:UpdateIndex",
            "aoss:DescribeIndex",
            "aoss:ReadDocument",
            "aoss:WriteDocument",
          ]
        },
        {
          ResourceType = "collection"
          Resource     = ["collection/${local.collection_name}"]
          Permission = [
            "aoss:CreateCollectionItems",
            "aoss:DeleteCollectionItems",
            "aoss:UpdateCollectionItems",
            "aoss:DescribeCollectionItems",
          ]
        }
      ]
      Principal = var.data_access_principal_arns
    }
  ])
}

# --- The SEARCH collection ---

resource "aws_opensearchserverless_collection" "this" {
  name = local.collection_name
  type = "SEARCH"

  tags = merge(local.common_tags, {
    Service = "search-service"
  })

  depends_on = [
    aws_opensearchserverless_security_policy.encryption,
    aws_opensearchserverless_security_policy.network,
  ]

  lifecycle {
    # AOSS collection and security-policy names must be <= 32 chars. The data
    # access policy name ("-data") is the longest of the derived names, so
    # guarding it guards them all. Fails fast at plan time instead of surfacing
    # an opaque AWS API error at apply for long project/namespace values that
    # still pass the per-variable regex validations.
    precondition {
      condition     = length(local.acc_policy_name) <= 32
      error_message = "Derived AOSS names exceed 32 chars: shorten var.project and/or var.namespace_suffix so that length(project + namespace_suffix) <= 26."
    }
  }
}
