import argparse
import fnmatch
import json
import sys

from control_report import assertion_report, load


def pairs(entries):
    for item in entries:
        yield item["action"].lower(), item["resource"]


def covers(pattern, target):
    return all(fnmatch.fnmatchcase(value, selector) for selector, value in zip(pattern, target))


def plan_policy(plan, address):
    matches = [c for c in plan["resource_changes"] if c["address"] == address]
    if len(matches) != 1 or matches[0]["type"] not in ("aws_iam_role_policy", "aws_iam_policy"):
        raise ValueError("approved address must identify exactly one IAM policy resource")
    change = matches[0]["change"]
    if (change.get("after_unknown") or {}).get("policy"):
        raise ValueError("policy is not known in the plan")
    return json.loads(change["after"]["policy"])


def evaluate(plan, scope):
    policy = plan_policy(plan, scope["address"])
    approved = set(pairs(scope["allow"]))
    if not approved or any(any(c in value for c in "*?[${") for pair in approved for value in pair):
        raise ValueError("approved scope must enumerate concrete actions and resources")
    statements = policy["Statement"]
    if isinstance(statements, dict):
        statements = [statements]
    allowed, denied = set(), set()
    for statement in statements:
        if set(statement) - {"Sid", "Effect", "Action", "Resource"}:
            raise ValueError("checker only supports unconditional Action/Resource statements")
        if statement["Effect"] not in ("Allow", "Deny"):
            raise ValueError("invalid policy effect")
        actions = statement["Action"]
        resources = statement["Resource"]
        actions = [actions] if isinstance(actions, str) else actions
        resources = [resources] if isinstance(resources, str) else resources
        if any("${" in value or "[" in value for value in (*actions, *resources)):
            raise ValueError("checker does not support policy variables or bracket patterns")
        target = allowed if statement["Effect"] == "Allow" else denied
        target.update((action.lower(), resource) for action in actions for resource in resources)

    rows = []
    for action, resource in sorted(approved):
        pair = action, resource
        permitted = any(covers(pattern, pair) for pattern in allowed) and not any(covers(pattern, pair) for pattern in denied)
        rows.append({"check": "approved path", "action": action, "resource": resource, "passed": permitted})
    for action, resource in sorted(allowed - approved - denied):
        if any(c in action + resource for c in "*?") or not any(covers(pattern, (action, resource)) for pattern in denied):
            rows.append({"check": "excess allow", "action": action, "resource": resource, "passed": False})
    return rows


def main():
    parser = argparse.ArgumentParser(description="Compare one offline IAM policy plan against a concrete approved scope")
    parser.add_argument("plan")
    parser.add_argument("scope")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        rows = evaluate(load(args.plan), load(args.scope))
        return assertion_report(args.output, "Offline IAM policy scope", rows, [
            ("check", "Check"), ("action", "Action"), ("resource", "Resource"), ("passed", "Passed"),
        ])
    except (KeyError, TypeError, ValueError, OSError) as error:
        print(f"IAM check did not run: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
