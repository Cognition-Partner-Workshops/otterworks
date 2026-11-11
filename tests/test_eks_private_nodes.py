import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text()


def test_nodes_use_private_subnets_without_public_ips():
    assert re.search(r'node_subnet_ids\s*=\s*module\.vpc\.private_subnet_ids', read('platform/terraform/main.tf'))
    private = re.search(r'resource "aws_subnet" "private" \{.*?\n\}', read('platform/terraform/modules/vpc/main.tf'), re.S)
    assert private and 'map_public_ip_on_launch = true' not in private.group(0)
    assert 'associatePublicIPAddress: false' in read('demo-platform/k8s/karpenter/nodepool.yaml')


def test_node_launch_template_stays_compatible_with_mixed_instance_types():
    template = re.search(r'resource "aws_launch_template" "node_group" \{.*?\n\}', read('platform/terraform/modules/eks/main.tf'), re.S)
    assert template and 'network_interfaces' not in template.group(0)


def test_keep_data_teardown_also_stops_the_nat_gateway():
    script = read('scripts/teardown-dev.sh')
    destroy = next(cmd for cmd in script.split('terraform -chdir=') if '-target=module.eks' in cmd)
    for target in ('module.eks', 'module.vpc.aws_nat_gateway.main', 'module.vpc.aws_eip.nat'):
        assert f'-target={target}' in destroy
