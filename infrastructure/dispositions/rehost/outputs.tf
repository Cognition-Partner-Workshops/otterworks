output "base_url" {
  description = "ALB URL for the rehosted application."
  value       = var.certificate_arn == null ? "http://${aws_lb.this.dns_name}" : "https://${var.public_hostname}"
}

output "instance_id" {
  value = aws_instance.this.id
}

output "artifact_bucket" {
  value = aws_s3_bucket.artifacts.id
}

output "app_log_group" {
  value = aws_cloudwatch_log_group.app.name
}

output "target_group_arn" {
  value = aws_lb_target_group.app.arn
}

output "alb_dns_name" {
  value = aws_lb.this.dns_name
}

output "expires" {
  value = var.expires
}
