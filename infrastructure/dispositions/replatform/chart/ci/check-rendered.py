#!/usr/bin/env python3
import argparse
import collections
import sys

import yaml


REQUIRED_LABEL = "otterworks.io/run-token"
REQUIRED_ANNOTATION = "otterworks.io/expires"


def check_metadata(metadata, location, errors):
    labels = metadata.get("labels") or {}
    annotations = metadata.get("annotations") or {}
    if not labels.get(REQUIRED_LABEL):
        errors.append(f"{location}: missing {REQUIRED_LABEL} label")
    if not annotations.get(REQUIRED_ANNOTATION):
        errors.append(f"{location}: missing {REQUIRED_ANNOTATION} annotation")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("rendered_yaml")
    parser.add_argument("--minimum-kinds", type=int, default=8)
    args = parser.parse_args()

    with open(args.rendered_yaml, encoding="utf-8") as stream:
        documents = [doc for doc in yaml.safe_load_all(stream) if doc]

    errors = []
    kinds = collections.Counter()
    pod_templates = 0
    for index, document in enumerate(documents):
        kind = document.get("kind", "<unknown>")
        kinds[kind] += 1
        metadata = document.get("metadata") or {}
        location = f"{kind}[{index}]"
        check_metadata(metadata, location, errors)

        if kind == "Service" and (document.get("spec") or {}).get("type") == "LoadBalancer":
            errors.append(f"{location}: LoadBalancer Services are not permitted")

        if kind == "NetworkPolicy":
            spec = document.get("spec") or {}
            for rule_index, rule in enumerate(spec.get("ingress") or []):
                peers = rule.get("from")
                if not peers:
                    errors.append(f"{location}.spec.ingress[{rule_index}]: empty from is not permitted")
                    continue
                for peer_index, peer in enumerate(peers):
                    if "namespaceSelector" in peer:
                        selector = peer.get("namespaceSelector") or {}
                        if not selector.get("matchLabels"):
                            errors.append(
                                f"{location}.spec.ingress[{rule_index}].from[{peer_index}]: "
                                "namespaceSelector must have matchLabels"
                            )
            if "Egress" in (spec.get("policyTypes") or []) and not (spec.get("egress") or []):
                errors.append(f"{location}.spec.egress: Egress policy must include rules")

        pod_template = ((document.get("spec") or {}).get("template") or {})
        if pod_template:
            pod_templates += 1
            check_metadata(pod_template.get("metadata") or {}, f"{location}.spec.template", errors)

    if len(kinds) < args.minimum_kinds:
        errors.append(
            f"expected at least {args.minimum_kinds} rendered kinds, got {len(kinds)}: {', '.join(sorted(kinds))}"
        )

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    print("Rendered resource counts:")
    for kind, count in sorted(kinds.items()):
        print(f"{kind:20} {count}")
    print(f"checked {len(documents)} resources and {pod_templates} pod templates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
