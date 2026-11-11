import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TF = ROOT / 'infrastructure/terraform/legacy-portal-ec2'


def block(text, header):
    match = re.search(re.escape(header) + r' \{.*?\n\}', text, re.S)
    assert match, header
    return match.group(0)


def test_custom_certificate_base_url_uses_its_domain():
    base_url = block((TF / 'outputs.tf').read_text(), 'output "base_url"')
    assert 'coalesce(var.domain_name, aws_lb.this.dns_name)' in base_url
    assert 'precondition' in base_url and 'var.certificate_arn == null || var.domain_name != null' in base_url
    assert 'variable "domain_name"' in (TF / 'variables.tf').read_text()
    assert '-var "domain_name=${DOMAIN_NAME}"' in (ROOT / 'scripts/lp-ec2.sh').read_text()


def test_plain_http_writes_are_refused_not_redirected():
    rule = block((TF / 'alb.tf').read_text(), 'resource "aws_lb_listener_rule" "http_writes"')
    assert 'aws_lb_listener.http_redirect.arn' in rule
    for method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        assert f'"{method}"' in rule
    assert 'fixed-response' in rule and 'status_code  = "426"' in rule
