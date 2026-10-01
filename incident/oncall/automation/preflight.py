"""Preflight check for the on-call storm automation (docs/oncall-storm/automation.md).

webhook:incoming triggers take no conditions, so this script is the
`status eq firing` condition: it starts a session only for a firing
Alertmanager group from the on-call storm route, and skips resolved
notifications and anything else that reaches the webhook URL.
Standard library only; reads $EVENT_FILE and writes $OUTPUT_FILE.
"""

import json
import os


def decide(event: dict) -> dict:
    body = (event.get("payload") or {}).get("body") or {}
    if not isinstance(body, dict):
        return {"run": False, "reason": "body is not an Alertmanager JSON object"}
    status = body.get("status")
    if status != "firing":
        return {"run": False, "reason": f"status is {status!r}, not 'firing'"}
    labels = body.get("commonLabels") or body.get("groupLabels") or {}
    if labels.get("page") != "oncall" and not any(
        (a.get("labels") or {}).get("page") == "oncall" for a in body.get("alerts") or []
    ):
        return {"run": False, "reason": "no alert carries page=oncall"}
    namespace = labels.get("namespace", "")
    if not namespace.startswith("otterworks-oncall-"):
        return {"run": False, "reason": f"namespace {namespace!r} is not an on-call tenant"}
    firing = sum(1 for a in body.get("alerts") or [] if a.get("status") == "firing")
    if firing == 0:
        return {"run": False, "reason": "group has no firing alerts"}
    return {"run": True}


def main() -> None:
    with open(os.environ["EVENT_FILE"], encoding="utf-8") as fh:
        event = json.load(fh)
    decision = decide(event)
    with open(os.environ["OUTPUT_FILE"], "w", encoding="utf-8") as fh:
        json.dump(decision, fh)
    print(json.dumps(decision))


if __name__ == "__main__":
    main()
