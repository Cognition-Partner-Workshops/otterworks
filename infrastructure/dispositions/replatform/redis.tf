resource "random_password" "redis" {
  count   = var.redis == null ? 0 : 1
  length  = 32
  special = false
}

resource "aws_elasticache_subnet_group" "redis" {
  count       = var.redis == null ? 0 : 1
  name        = "${local.name}-redis"
  description = "Private subnets for ${var.service_name} run ${local.name}"
  subnet_ids  = var.subnet_ids
  tags        = local.tags
}

resource "aws_security_group" "redis" {
  count       = var.redis == null ? 0 : 1
  name        = "${local.name}-redis"
  description = "Redis for ${var.service_name} run ${local.name}; workload clients only"
  vpc_id      = var.vpc_id
  tags        = merge(local.tags, { Name = "${local.name}-redis" })
}

resource "aws_vpc_security_group_ingress_rule" "redis" {
  for_each                     = var.redis == null ? {} : local.client_rules
  security_group_id            = aws_security_group.redis[0].id
  description                  = "Redis from ${each.key}"
  referenced_security_group_id = each.value.security_group_id
  cidr_ipv4                    = each.value.cidr
  from_port                    = 6379
  to_port                      = 6379
  ip_protocol                  = "tcp"
  tags                         = local.tags
}

resource "aws_elasticache_replication_group" "redis" {
  count                      = var.redis == null ? 0 : 1
  replication_group_id       = "${local.name}-redis"
  description                = "Redis for ${var.service_name} run ${local.name}"
  engine                     = "redis"
  engine_version             = var.redis.engine_version
  node_type                  = var.redis.node_type
  num_cache_clusters         = var.redis.num_cache_clusters
  automatic_failover_enabled = var.redis.num_cache_clusters > 1
  multi_az_enabled           = var.redis.num_cache_clusters > 1
  port                       = 6379
  subnet_group_name          = aws_elasticache_subnet_group.redis[0].name
  security_group_ids         = [aws_security_group.redis[0].id]
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = random_password.redis[0].result
  apply_immediately          = true
  snapshot_retention_limit   = 0
  tags                       = local.tags

  depends_on = [terraform_data.inputs]
}
