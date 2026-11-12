"""Validate all frozen contracts plus a missing policy against pinned OpenAPI 3.1 schemas."""
import argparse
from collections import Counter
import jsonschema
import yaml
from common import ROOT, OPERATIONS, base_url, endpoint, fetch, records, write_report


def validator(spec, op, status):
    operation = spec["paths"][f"/v1/policies/{{policyNumber}}/{op}"]["get"]
    response = operation["responses"].get(str(status))
    if response is None:
        raise ValueError(f"Undocumented HTTP status {status}")
    while "$ref" in response:
        pointer = response["$ref"]
        if not pointer.startswith("#/"):
            raise ValueError("Only pinned local refs supported")
        response = spec
        for token in pointer[2:].split("/"):
            response = response[token]
    schema = dict(response["content"]["application/json"]["schema"])
    schema["components"] = spec["components"]
    return jsonschema.Draft202012Validator(schema, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--op", required=True, choices=OPERATIONS)
    parser.add_argument("--ns", default="iri")
    parser.add_argument("--not-found", default="9999999999", help="Contract known to be absent (must return 404)")
    args = parser.parse_args()
    spec = yaml.safe_load((ROOT / "vendor/iri-policy-inquiry-v1.1.5/PolicyInquiry_v1.1.5.yml").read_text())
    frozen = records(args.op)
    if args.not_found in {str(r["contract"]) for r in frozen}:
        parser.error("--not-found must not be a frozen contract")
    responses = []
    for contract, missing in [(r["contract"], False) for r in frozen] + [(args.not_found, True)]:
        errors = []
        try:
            status, body = fetch(endpoint(base_url(args.ns), args.op, contract))
            if status != (404 if missing else 200):
                errors.append(f"Expected HTTP {404 if missing else 200}, got {status}")
            for error in sorted(validator(spec, args.op, status).iter_errors(body), key=lambda e: str(list(e.path))):
                errors.append(f"{list(error.path)}: {error.message}")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(str(exc))
        responses.append(dict(contract=contract, counts={"fail" if errors else "pass": 1}, errors=errors))
    summary = Counter()
    for response in responses:
        summary.update(response["counts"])
    write_report(args.op, "schema", dict(summary=dict(summary, responses=len(responses)), responses=responses))
    return bool(summary["fail"])


if __name__ == "__main__":
    raise SystemExit(main())
