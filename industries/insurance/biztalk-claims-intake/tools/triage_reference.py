#!/usr/bin/env python3
"""Reference evaluation of the ClaimTriage BRE policy over the TriageFacts goldens.

BizTalk Server is not installed anywhere near this fixture, so the policy's expected outcomes
come from this evaluator, which reads Rules/ClaimTriagePolicy.xml and applies the same agenda
semantics the Rule Engine uses here: rules fire in descending priority, the first rule to set
Outcome wins (later rules test for an empty Outcome), and every fired rule appends its Reason.
Writes corpus/golden/triage/<claim>.json and the table corpus/golden/triage/SUMMARY.md.
"""
from __future__ import annotations

import json
import os
import sys
import xml.etree.ElementTree as ET
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BRL = "{http://schemas.microsoft.com/businessruleslanguage/2002}"
IN_LIST_HELPER = "InList"


def field_of(xpath: str) -> str:
    return xpath.rsplit("local-name()='", 1)[1].split("'")[0]


def const_of(node: ET.Element):
    child = list(node)[0]
    text = child.text or ""
    kind = child.tag.replace(BRL, "")
    if kind == "boolean":
        return text == "true"
    if kind == "int":
        return int(text)
    if kind == "decimal":
        return Decimal(text)
    return text


def evaluate_condition(node: ET.Element, facts: dict) -> bool:
    tag = node.tag.replace(BRL, "")
    if tag == "and":
        return all(evaluate_condition(c, facts) for c in node)
    if tag == "or":
        return any(evaluate_condition(c, facts) for c in node)
    if tag == "function":
        member = node.find(f"{BRL}classmember")
        if member.get("member") == IN_LIST_HELPER:
            args = member.findall(f"{BRL}argument")
            value = facts[field_of(args[0].find(f"{BRL}xmldocumentmember").get("xpath"))]
            allowed = const_of(args[1].find(f"{BRL}constant")).split(",")
            return value in allowed
        raise ValueError(member.get("member"))
    member, constant = list(node)
    left = facts[field_of(member.get("xpath"))]
    right = const_of(constant)
    if isinstance(right, bool):
        left = left == "true" if isinstance(left, str) else left
    elif isinstance(right, Decimal):
        left = Decimal(left)
    elif isinstance(right, int):
        left = int(left)
    return {
        "equal": left == right,
        "notequal": left != right,
        "greaterthan": left > right,
        "greaterthanequal": left >= right,
        "lessthan": left < right,
        "lessthanequal": left <= right,
    }[tag]


def load_rules(policy_path: str):
    root = ET.parse(policy_path).getroot()
    rules = []
    for rule in root.iter(f"{BRL}rule"):
        if rule.get("active") != "true":
            continue
        then = rule.find(f"{BRL}then")
        outcome = None
        reason = None
        for fn in then.findall(f"{BRL}function"):
            member = fn.find(f"{BRL}xmldocumentmember")
            if member is not None and field_of(member.get("xpath")) == "Outcome":
                outcome = fn.find(f".//{BRL}constant/{BRL}string").text
            classmember = fn.find(f"{BRL}classmember")
            if classmember is not None and classmember.get("member") == "AddReason":
                reason = classmember.findall(f"{BRL}argument")[1].find(f".//{BRL}string").text
        rules.append((int(rule.get("priority")), rule.get("name"), list(rule.find(f"{BRL}if"))[0], outcome, reason))
    rules.sort(key=lambda r: -r[0])
    return rules


def evaluate(facts: dict, rules) -> dict:
    facts = dict(facts)
    facts["Outcome"] = ""
    fired = []
    reasons = []
    for priority, name, condition, outcome, reason in rules:
        if evaluate_condition(condition, facts):
            fired.append(name)
            reasons.append(reason)
            if facts["Outcome"] == "":
                facts["Outcome"] = outcome
    return {"ClaimNumber": facts["ClaimNumber"], "Outcome": facts["Outcome"], "Reasons": reasons, "RulesFired": fired}


def main() -> int:
    rules = load_rules(os.path.join(ROOT, "Rules", "ClaimTriagePolicy.xml"))
    src = os.path.join(ROOT, "corpus", "golden", "triage-facts")
    dst = os.path.join(ROOT, "corpus", "golden", "triage")
    check = len(sys.argv) > 1 and sys.argv[1] == "check"
    os.makedirs(dst, exist_ok=True)
    failures = 0
    rows = []
    for name in sorted(os.listdir(src)):
        root = ET.parse(os.path.join(src, name)).getroot()
        facts = {child.tag: child.text for child in root}
        result = evaluate(facts, rules)
        rows.append(result)
        payload = (json.dumps(result, indent=2) + "\n").encode("utf-8")
        target = os.path.join(dst, name.replace(".xml", ".json"))
        if check:
            with open(target, "rb") as fh:
                if fh.read() != payload:
                    failures += 1
                    print(f"  DIFF    {name}")
        else:
            with open(target, "wb") as fh:
                fh.write(payload)
    summary = ["| Claim | Outcome | Rules fired |", "| --- | --- | --- |"]
    summary += [f"| {r['ClaimNumber']} | {r['Outcome']} | {', '.join(r['RulesFired'])} |" for r in rows]
    counts = {}
    for r in rows:
        counts[r["Outcome"]] = counts.get(r["Outcome"], 0) + 1
    summary += ["", "| Outcome | Claims |", "| --- | --- |"] + [f"| {k} | {v} |" for k, v in sorted(counts.items())]
    text = ("\n".join(summary) + "\n").encode("utf-8")
    summary_path = os.path.join(dst, "SUMMARY.md")
    if check:
        with open(summary_path, "rb") as fh:
            if fh.read() != text:
                failures += 1
                print("  DIFF    SUMMARY.md")
    else:
        with open(summary_path, "wb") as fh:
            fh.write(text)
    print(f"triage: {len(rows)} claims, failures {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
