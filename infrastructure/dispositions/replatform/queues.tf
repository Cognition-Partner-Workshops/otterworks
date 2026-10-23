locals {
  queue_names = {
    for key, settings in var.queues : key => "${local.name}-${key}${settings.fifo ? ".fifo" : ""}"
  }
  dlq_names = {
    for key, settings in var.queues : key => "${local.name}-${key}-dlq${settings.fifo ? ".fifo" : ""}"
  }
}

resource "aws_sqs_queue" "dlq" {
  for_each                  = var.queues
  name                      = local.dlq_names[each.key]
  fifo_queue                = each.value.fifo
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
  tags                      = local.tags
}

resource "aws_sqs_queue" "this" {
  for_each                   = var.queues
  name                       = local.queue_names[each.key]
  fifo_queue                 = each.value.fifo
  visibility_timeout_seconds = each.value.visibility_timeout_seconds
  message_retention_seconds  = each.value.message_retention_seconds
  sqs_managed_sse_enabled    = true
  tags                       = local.tags

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq[each.key].arn
    maxReceiveCount     = each.value.max_receive_count
  })
}
