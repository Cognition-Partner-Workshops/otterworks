import argparse
import ipaddress
import json
import subprocess
import sys

import yaml

from control_report import assertion_report, load


PROBE = """
import socket, sys
try:
    with socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=3):
        pass
except TimeoutError:
    print('denied')
except OSError:
    print('error')
else:
    print('allowed')
"""


def matches(selector, labels):
    if not all(labels.get(key) == value for key, value in selector.get("matchLabels", {}).items()):
        return False
    for item in selector.get("matchExpressions", []):
        key, op, values = item["key"], item["operator"], item.get("values", [])
        satisfied = {
            "In": key in labels and labels[key] in values,
            "NotIn": key not in labels or labels[key] not in values,
            "Exists": key in labels,
            "DoesNotExist": key not in labels,
        }
        if not satisfied[op]:
            return False
    return True


def peer_matches(peer, pod, policy_namespace, namespaces):
    if "ipBlock" in peer:
        if not pod.get("ip"):
            raise ValueError("offline ipBlock evaluation requires a peer IP in the matrix inventory")
        address = ipaddress.ip_address(pod["ip"])
        block = peer["ipBlock"]
        return address in ipaddress.ip_network(block["cidr"]) and not any(
            address in ipaddress.ip_network(cidr) for cidr in block.get("except", [])
        )
    if "namespaceSelector" in peer:
        if not matches(peer["namespaceSelector"], namespaces[pod["namespace"]]):
            return False
    elif "podSelector" in peer and pod["namespace"] != policy_namespace:
        return False
    return "podSelector" not in peer or matches(peer["podSelector"], pod.get("labels", {}))


def port_matches(spec, dest, protocol, port):
    if spec.get("protocol", "TCP") != protocol:
        return False
    if "port" not in spec:
        return True
    start = spec["port"]
    if isinstance(start, str):
        return any(p["name"] == start and p["port"] == port and p.get("protocol", "TCP") == protocol
                   for p in dest.get("ports", []))
    return start <= port <= spec.get("endPort", start)


def offline_allowed(policies, namespaces, source, destination, protocol, port):
    def direction(key, subject, other, peers):
        selected = []
        for policy in policies:
            namespace = policy["metadata"].get("namespace", "default")
            spec = policy["spec"]
            defaults = ["Ingress", "Egress"] if spec.get("egress") else ["Ingress"]
            if (namespace == subject["namespace"] and key.title() in spec.get("policyTypes", defaults)
                    and matches(spec["podSelector"], subject.get("labels", {}))):
                selected.append((namespace, spec))
        if not selected:
            return True
        return any(
            (not rule.get(peers) or any(peer_matches(peer, other, namespace, namespaces) for peer in rule[peers]))
            and (not rule.get("ports") or any(port_matches(p, destination, protocol, port) for p in rule["ports"]))
            for namespace, spec in selected for rule in spec.get(key, [])
        )

    return direction("egress", source, destination, "to") and direction("ingress", destination, source, "from")


def policies_from(paths):
    def extract(doc):
        if doc and doc.get("kind") in ("List", "NetworkPolicyList"):
            return [policy for item in doc["items"] for policy in extract(item)]
        return [doc] if doc and doc.get("kind") == "NetworkPolicy" else []

    output = []
    for path in paths:
        with open(path) as source:
            output.extend(policy for doc in yaml.safe_load_all(source) for policy in extract(doc))
    if not output:
        raise ValueError("no NetworkPolicy objects found")
    return output


def live_probe(context, source, destination, protocol, port):
    if protocol != "TCP":
        raise ValueError("live mode supports TCP only")
    dest = subprocess.check_output([
        "kubectl", "--context", context, "-n", destination["namespace"],
        "get", "pod", destination["pod"], "-o", "json",
    ], text=True, timeout=15)
    address = json.loads(dest)["status"]["podIP"]
    result = subprocess.check_output([
        "kubectl", "--context", context, "-n", source["namespace"], "exec", source["pod"],
        "--", "python3", "-c", PROBE, address, str(port),
    ], text=True, timeout=15).strip()
    if result not in ("allowed", "denied", "error"):
        raise ValueError("unexpected probe output")
    return result


def run(matrix, probe):
    rows = []
    for check in matrix["checks"]:
        src, dst, port = (check[k] for k in ("source", "destination", "port"))
        protocol = check.get("protocol", "TCP")
        expected = check["expected"]
        if expected not in ("allow", "deny") or type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("expected allow/deny and a numeric port in range")
        actual = probe(matrix["pods"][src], matrix["pods"][dst], protocol, port)
        rows.append({"source": src, "destination": dst, "port": port, "protocol": protocol,
                     "expected": expected, "actual": actual,
                     "passed": actual == {"allow": "allowed", "deny": "denied"}[expected]})
    if not rows:
        raise ValueError("matrix cannot be empty")
    return rows


def main():
    parser = argparse.ArgumentParser(description="Check approved pod-to-pod connectivity")
    parser.add_argument("matrix")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--policy", nargs="+", help="Offline mode: rendered NetworkPolicy files")
    mode.add_argument("--kind", metavar="NAME", help="Live mode: name of a kind cluster")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        matrix = load(args.matrix)
        if args.policy:
            policies = policies_from(args.policy)
            namespaces = {ns: {**labels, "kubernetes.io/metadata.name": ns}
                          for ns, labels in matrix["namespaces"].items()}

            def probe(src, dst, protocol, port):
                return "allowed" if offline_allowed(policies, namespaces, src, dst, protocol, port) else "denied"
        else:
            clusters = subprocess.check_output(["kind", "get", "clusters"], text=True, timeout=15).splitlines()
            if args.kind not in clusters:
                raise ValueError("requested local kind cluster does not exist")

            def probe(src, dst, protocol, port):
                return live_probe("kind-" + args.kind, src, dst, protocol, port)

        rows = run(matrix, probe)
        return assertion_report(args.output, "Connectivity matrix", rows, [
            ("source", "Source"), ("destination", "Destination"), ("protocol", "Protocol"), ("port", "Port"),
            ("expected", "Expected"), ("actual", "Actual"), ("passed", "Passed"),
        ])
    except (KeyError, ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"Connectivity check did not run: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
