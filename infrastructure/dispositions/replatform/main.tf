locals {
  name = var.run_token

  tags = merge(var.extra_tags, {
    run_token            = var.run_token
    RunToken             = var.run_token
    Expires              = var.expires
    ManagedBy            = "terraform"
    disposition          = "replatform"
    service              = var.service_name
    disposition_evidence = var.disposition_evidence
  })

  service_account_name = coalesce(var.service_account_name, var.service_name)
  network_needed       = var.postgres != null || var.redis != null
  name_suffix          = substr(sha1(var.service_name), 0, 6)

  client_rules = merge(
    { for id in var.client_security_group_ids : id => { security_group_id = id, cidr = null } },
    { for cidr in var.client_cidr_blocks : "cidr-${replace(cidr, "/", "-")}" => { security_group_id = null, cidr = cidr } },
  )

  # Each managed dependency the release consumes, for the replatform evidence annotation.
  managed_targets = compact(concat(
    var.postgres == null ? [] : ["postgres=rds"],
    var.redis == null ? [] : ["redis=elasticache"],
    [for key, _ in var.buckets : "${key}=s3"],
    [for key, _ in var.queues : "${key}=sqs"],
  ))
}

data "aws_partition" "current" {}

data "aws_region" "current" {}

resource "terraform_data" "inputs" {
  input = local.name

  lifecycle {
    precondition {
      condition     = !local.network_needed || (var.vpc_id != null && length(var.subnet_ids) >= 2)
      error_message = "postgres and redis need vpc_id and at least two private subnet_ids."
    }

    precondition {
      condition     = !local.network_needed || length(local.client_rules) > 0
      error_message = "postgres and redis need client_security_group_ids or client_cidr_blocks so the workload can reach them."
    }

    precondition {
      condition     = !var.deploy_release || (var.image_repository != "" && var.image_tag != "")
      error_message = "deploy_release needs image_repository and image_tag."
    }
  }
}
