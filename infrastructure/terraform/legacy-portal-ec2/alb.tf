# Internet-facing HTTP-only ALB in front of the monolith host, the way the
# on-prem deployment is reached today. No TLS listener: the "before" state
# serves plain HTTP.

resource "aws_lb" "this" { # nosemgrep: terraform.aws.security.aws-elb-access-logs-not-enabled.aws-elb-access-logs-not-enabled
  name               = local.name
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = data.aws_subnets.public.ids
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

resource "aws_lb_listener" "http" { # nosemgrep: terraform.aws.security.insecure-load-balancer-tls-version.insecure-load-balancer-tls-version
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}
