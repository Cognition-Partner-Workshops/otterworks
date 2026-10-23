locals {
  connection_config = merge(
    { AWS_REGION = data.aws_region.current.name },
    var.postgres == null ? {} : {
      DB_HOST       = aws_db_instance.postgres[0].address
      DB_PORT       = tostring(aws_db_instance.postgres[0].port)
      DB_NAME       = var.postgres.database_name
      DB_USER       = var.postgres.username
      DB_SSLMODE    = "require"
      DB_SECRET_ARN = aws_secretsmanager_secret.postgres[0].arn
    },
    var.redis == null ? {} : {
      REDIS_HOST = aws_elasticache_replication_group.redis[0].primary_endpoint_address
      REDIS_PORT = "6379"
      REDIS_TLS  = "true"
    },
    { for key, bucket in aws_s3_bucket.this : "S3_BUCKET_${upper(replace(key, "-", "_"))}" => bucket.id },
    { for key, queue in aws_sqs_queue.this : "SQS_QUEUE_URL_${upper(replace(key, "-", "_"))}" => queue.url },
  )

  connection_secrets = merge(
    var.postgres == null ? {} : { DB_PASSWORD = random_password.postgres[0].result },
    var.redis == null ? {} : { REDIS_AUTH_TOKEN = random_password.redis[0].result },
  )

  upgrade_paths_annotation = join("; ", [for component, path in var.upgrade_paths : "${component}: ${path}"])

  ingress_values = var.ingress_host == null ? [] : [yamlencode({
    ingress = {
      enabled   = true
      className = "nginx"
      hosts = [{
        host  = var.ingress_host
        paths = [{ path = "/", pathType = "Prefix" }]
      }]
    }
  })]

  chart_values = {
    nameOverride        = var.service_name
    fullnameOverride    = var.service_name
    runToken            = var.run_token
    expires             = var.expires
    dispositionEvidence = var.disposition_evidence
    replicaCount        = var.replicas
    containerPort       = var.container_port
    image = {
      repository = var.image_repository
      tag        = var.image_tag
    }
    healthCheck = {
      path = var.health_check_path
    }
    serviceAccount = {
      create  = true
      name    = local.service_account_name
      roleArn = local.irsa_enabled ? aws_iam_role.service_account[0].arn : ""
    }
    config = merge(var.environment, local.connection_config)
    podAnnotations = {
      "otterworks.io/managed-targets" = join(",", local.managed_targets)
      "otterworks.io/upgrade-paths"   = local.upgrade_paths_annotation
    }
  }
}

resource "helm_release" "this" {
  count            = var.deploy_release ? 1 : 0
  name             = var.service_name
  chart            = "${path.module}/chart"
  namespace        = var.namespace
  create_namespace = false
  atomic           = true
  wait             = true
  timeout          = var.helm_timeout_seconds
  values           = concat([yamlencode(local.chart_values)], local.ingress_values, var.chart_values)

  dynamic "set_sensitive" {
    for_each = local.connection_secrets
    content {
      name  = "secrets.${set_sensitive.key}"
      value = set_sensitive.value
    }
  }

  depends_on = [
    terraform_data.inputs,
    aws_iam_role_policy.service_account,
    aws_secretsmanager_secret_version.postgres,
  ]
}
