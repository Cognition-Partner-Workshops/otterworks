# Internet-facing ALB in front of the monolith host. Clients reach it over
# HTTPS only; port 80 answers with a permanent redirect to 443. The ALB talks
# plain HTTP to the instance inside the VPC, where the instance security group
# admits only this load balancer.

resource "aws_lb" "this" {
  name               = local.name
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = data.aws_subnets.public.ids

  access_logs {
    bucket  = module.access_logs.id
    prefix  = "alb"
    enabled = true
  }
}

resource "aws_lb_target_group" "app" {
  name     = "${local.name}-app"
  port     = var.app_port
  protocol = "HTTP"
  vpc_id   = data.aws_vpc.this.id

  health_check {
    path                = "/health"
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_target_group_attachment" "app" {
  target_group_arn = aws_lb_target_group.app.arn
  target_id        = aws_instance.this.id
  port             = var.app_port
}

# The ALB has no DNS name of its own to validate an ACM certificate against,
# so unless var.certificate_arn names one, each run imports a self-signed
# certificate for the ALB's DNS name. lp-ec2.sh writes its PEM next to the run
# transcripts and trusts it for curl and replay.py.
resource "tls_private_key" "alb" {
  count     = var.certificate_arn == null ? 1 : 0
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "tls_self_signed_cert" "alb" {
  count           = var.certificate_arn == null ? 1 : 0
  private_key_pem = tls_private_key.alb[0].private_key_pem

  subject {
    common_name  = local.name
    organization = "OtterWorks legacy-portal-ec2"
  }

  dns_names             = [aws_lb.this.dns_name]
  validity_period_hours = 24 * 30
  allowed_uses          = ["key_encipherment", "digital_signature", "server_auth"]
}

resource "aws_acm_certificate" "alb" {
  count            = var.certificate_arn == null ? 1 : 0
  private_key      = tls_private_key.alb[0].private_key_pem
  certificate_body = tls_self_signed_cert.alb[0].cert_pem

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.this.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = coalesce(var.certificate_arn, try(aws_acm_certificate.alb[0].arn, null))

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

resource "aws_lb_listener" "http_redirect" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      protocol    = "HTTPS"
      port        = "443"
      status_code = "HTTP_301"
    }
  }
}

# ALB redirects are 301/302 only, and clients replay those as GET, so a write
# sent to port 80 would be silently dropped. Refuse it instead. ALB allows at
# most three values per condition, so the methods are split across two rules.
resource "aws_lb_listener_rule" "http_writes" {
  for_each = {
    "1" = ["POST", "PUT", "PATCH"]
    "2" = ["DELETE"]
  }

  listener_arn = aws_lb_listener.http_redirect.arn
  priority     = tonumber(each.key)

  condition {
    http_request_method {
      values = each.value
    }
  }

  action {
    type = "fixed-response"

    fixed_response {
      content_type = "text/plain"
      message_body = "Use HTTPS: writes are not redirected from HTTP."
      status_code  = "426"
    }
  }
}
