resource "aws_security_group" "alb" {
  name        = "${var.run_token}-alb"
  description = "ALB for ${var.service_name} rehost run ${var.run_token}"
  vpc_id      = var.vpc_id
  tags        = merge(local.tags, { Name = "${var.run_token}-alb" })
}

resource "aws_vpc_security_group_ingress_rule" "alb" {
  for_each          = local.alb_ingress_rules
  security_group_id = aws_security_group.alb.id
  description       = "${upper(each.value.listener)} from configured CIDR"
  cidr_ipv4         = each.value.cidr
  from_port         = each.value.port
  to_port           = each.value.port
  ip_protocol       = "tcp"
  tags              = local.tags
}

resource "aws_vpc_security_group_egress_rule" "alb" {
  security_group_id = aws_security_group.alb.id
  description       = "All egress"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
  tags              = local.tags
}

resource "aws_security_group" "instance" {
  name        = "${var.run_token}-instance"
  description = "Only the run ALB can reach ${var.service_name}"
  vpc_id      = var.vpc_id
  tags        = merge(local.tags, { Name = "${var.run_token}-instance" })
}

resource "aws_vpc_security_group_ingress_rule" "instance_app_from_alb" {
  security_group_id            = aws_security_group.instance.id
  description                  = "Application port from the ALB only"
  referenced_security_group_id = aws_security_group.alb.id
  from_port                    = var.app_port
  to_port                      = var.app_port
  ip_protocol                  = "tcp"
  tags                         = local.tags
}

resource "aws_vpc_security_group_egress_rule" "instance" {
  security_group_id = aws_security_group.instance.id
  description       = "All egress for package, SSM, CloudWatch, and S3 access"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
  tags              = local.tags
}

resource "aws_lb" "this" { # nosemgrep: terraform.aws.security.aws-elb-access-logs-not-enabled.aws-elb-access-logs-not-enabled
  name               = var.run_token
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.subnet_ids
  tags               = merge(local.tags, { Name = var.run_token })
}

resource "aws_lb_target_group" "app" {
  name     = "${var.run_token}-app"
  port     = var.app_port
  protocol = "HTTP"
  vpc_id   = var.vpc_id
  tags     = merge(local.tags, { Name = "${var.run_token}-app" })

  health_check {
    path                = var.health_check_path
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

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP" # nosemgrep: terraform.aws.security.insecure-load-balancer-tls-version.insecure-load-balancer-tls-version
  tags              = local.tags

  default_action {
    type = var.certificate_arn == null ? "forward" : "redirect"

    dynamic "redirect" {
      for_each = var.certificate_arn == null ? [] : [true]
      content {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }

    target_group_arn = var.certificate_arn == null ? aws_lb_target_group.app.arn : null
  }
}

resource "aws_lb_listener" "https" {
  count             = var.certificate_arn == null ? 0 : 1
  load_balancer_arn = aws_lb.this.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn
  tags              = local.tags

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}
