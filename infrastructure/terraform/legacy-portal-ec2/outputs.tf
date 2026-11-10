output "base_url" {
  description = "HTTPS URL of the internet-facing ALB. lp-ec2-replay uses it as the target base URL."
  value       = "https://${aws_lb.this.dns_name}"
}

output "alb_ca_cert_pem" {
  description = "Self-signed certificate on the HTTPS listener, empty when var.certificate_arn is set. lp-ec2.sh trusts it for curl and replay.py."
  value       = try(tls_self_signed_cert.alb[0].cert_pem, "")
}

output "instance_id" {
  value = aws_instance.this.id
}

output "instance_type" {
  value = aws_instance.this.instance_type
}

output "artifact_bucket" {
  value = aws_s3_bucket.artifacts.id
}

output "app_log_group" {
  value = aws_cloudwatch_log_group.app.name
}

output "target_group_arn" {
  description = "Used by lp-ec2-up to wait for the health check."
  value       = aws_lb_target_group.app.arn
}

output "expires" {
  value = var.expires
}
