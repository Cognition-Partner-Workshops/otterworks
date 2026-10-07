#!/usr/bin/env python3
"""List what the devin-aws-engineer role did, from CloudTrail lookup-events.

Run under the observer role (cloudworker/assume.sh observer ...). Pulls every
management event since --start (both ReadOnly=false and ReadOnly=true), keeps
the ones whose sessionIssuer is --role-arn (default CW_ENGINEER_ROLE_ARN), and
prints a markdown table of the write events (time, event, resource, session,
ticket) plus read-only counts per session. Each write is also checked against
--token: a resource is flagged when none of its names contains the token
(dashes or underscores) and it is not on the --allow list.

Usage:
    python3 scripts/cloudtrail-engineer-actions.py --start 2026-10-06T08:45:00Z \
        --token lp-20261006-bd [--session-map devin-xxx=UNT2-4 ...] [--json FILE]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

import boto3

# Request fields that name the thing an API call acted on.
NAME_KEYS = (
    "functionName", "bucketName", "name", "Name", "roleName", "policyName", "policyArn",
    "secretId", "dBInstanceIdentifier", "dBSubnetGroupName", "groupName", "groupId",
    "workGroup", "databaseName", "tableName", "logGroupName", "resourceArn", "resourceARN",
    "arn", "ruleName", "scheduleName", "keyId", "repositoryName", "instanceProfileName",
    "queryExecutionId", "namedQueryId", "streamName", "topicArn", "queueUrl", "Resource",
    "ResourceArn", "resourceName", "statementId", "layerName", "clusterName",
    "granteePrincipal", "aws:lambda:FunctionArn",
)
# Response fields holding the generated id of a resource created under a name.
ID_KEYS = ("groupId", "functionArn", "roleId", "arn")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--start", required=True, help="RFC 3339 start time")
    p.add_argument("--end", help="RFC 3339 end time (default now)")
    p.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    p.add_argument("--role-arn", default=os.environ.get("CW_ENGINEER_ROLE_ARN"))
    p.add_argument("--token", required=True, help="run token, e.g. lp-20261006-bd")
    p.add_argument("--allow", action="append", default=[],
                   help="regex for resource names that are expected outside the token")
    p.add_argument("--session-map", action="append", default=[], metavar="SESSION=TICKET")
    p.add_argument("--json", help="write the filtered raw events here")
    p.add_argument("--from-json", help="read events saved by --json instead of calling CloudTrail")
    p.add_argument("--only-mapped", action="store_true",
                   help="report only the sessions given with --session-map")
    return p.parse_args()


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def lookup(ct, start, end, read_only: str):
    kwargs = dict(StartTime=start, EndTime=end, MaxResults=50,
                  LookupAttributes=[{"AttributeKey": "ReadOnly", "AttributeValue": read_only}])
    for page in ct.get_paginator("lookup_events").paginate(**kwargs):
        yield from page["Events"]


def names_of(detail: dict) -> list[str]:
    out = [n for n in detail.get("_resources") or [] if n]
    out += [r.get("ARN") for r in detail.get("resources") or [] if r.get("ARN")]
    stack = [detail.get("requestParameters") or {}]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                if k in NAME_KEYS and isinstance(v, str):
                    out.append(v)
                elif isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(cur, list):
            stack.extend(cur)
    for k in ("functionName", "functionArn", "dBInstanceArn", "arn", "name"):
        v = (detail.get("responseElements") or {}).get(k) if isinstance(detail.get("responseElements"), dict) else None
        if isinstance(v, str):
            out.append(v)
    seen, uniq = set(), []
    for n in out:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    return uniq


def main() -> int:
    a = parse_args()
    if not a.role_arn:
        sys.exit("--role-arn or CW_ENGINEER_ROLE_ARN is required")
    start = ts(a.start)
    end = ts(a.end) if a.end else datetime.now(timezone.utc)
    smap = dict(x.split("=", 1) for x in a.session_map)
    tok = re.compile(re.escape(a.token).replace(r"\-", "[-_]"), re.I)
    allow = [re.compile(x) for x in a.allow]

    raw = []
    if a.from_json:
        with open(a.from_json) as fh:
            raw = json.load(fh)
    else:
        ct = boto3.client("cloudtrail", region_name=a.region)
        for ro in ("false", "true"):
            for ev in lookup(ct, start, end, ro):
                d = json.loads(ev["CloudTrailEvent"])
                issuer = (((d.get("userIdentity") or {}).get("sessionContext") or {})
                          .get("sessionIssuer") or {}).get("arn")
                if issuer == a.role_arn:
                    d["_resources"] = [r.get("ResourceName") for r in ev.get("Resources", [])]
                    raw.append(d)
    raw.sort(key=lambda d: d["eventTime"])

    # Ids generated for resources created under a token name count as token-owned.
    owned: set[str] = set()
    for d in raw:
        resp = d.get("responseElements")
        if isinstance(resp, dict) and any(tok.search(n) for n in names_of(d)):
            for k in ID_KEYS:
                if isinstance(resp.get(k), str):
                    owned.add(resp[k])

    writes, reads = [], defaultdict(Counter)
    for d in raw:
        session = d["userIdentity"]["arn"].rsplit("/", 1)[-1]
        if a.only_mapped and session not in smap:
            continue
        name = d["eventName"]
        if d.get("readOnly") or re.match(r"(Describe|Get|List|Head|Lookup|Search)", name):
            reads[session][name] += 1
            continue
        names = names_of(d)
        outside = bool(names) and not any(
            tok.search(n) or n in owned or any(r.search(n) for r in allow) for n in names)
        writes.append(dict(time=ts(d["eventTime"]).strftime("%Y-%m-%dT%H:%M:%SZ"),
                           event=f"{d.get('eventSource','').split('.')[0]}:{name}",
                           resource=", ".join(names[:3]) or "-", session=session,
                           ticket=smap.get(session, "?"), error=d.get("errorCode", ""),
                           outside=outside, unnamed=not names))
    writes.sort(key=lambda w: w["time"])

    print(f"Engineer role `{a.role_arn.rsplit('/',1)[-1]}` in {a.region}, {start:%Y-%m-%dT%H:%MZ} .. {end:%Y-%m-%dT%H:%MZ}\n")
    print("| Event time (UTC) | Event | Resource | Session | Ticket | Error |")
    print("| --- | --- | --- | --- | --- | --- |")
    for w in writes:
        flag = " **(outside token)**" if w["outside"] else ""
        print(f"| {w['time']} | {w['event']} | {w['resource']}{flag} | {w['session']} | {w['ticket']} | {w['error']} |")
    print("\nWrite events per session:\n")
    per = Counter((w["session"], w["ticket"]) for w in writes)
    print("| Session | Ticket | Writes | Failed | Read-only calls |")
    print("| --- | --- | --- | --- | --- |")
    sessions = sorted(set(s for s, _ in per) | set(reads))
    for s in sessions:
        n = sum(v for (ss, _), v in per.items() if ss == s)
        f = sum(1 for w in writes if w["session"] == s and w["error"])
        print(f"| {s} | {smap.get(s,'?')} | {n} | {f} | {sum(reads[s].values())} |")
    outside = [w for w in writes if w["outside"] and not w["error"]]
    unnamed = [w for w in writes if w["unnamed"] and not w["error"]]
    print(f"\nSuccessful writes on resources outside `{a.token}`: {len(outside)}")
    for w in outside:
        print(f"- {w['time']} {w['event']} {w['resource']} ({w['session']})")
    print(f"Successful writes with no resource name in the event: {len(unnamed)}")
    for w in unnamed:
        print(f"- {w['time']} {w['event']} ({w['session']})")
    if a.json and not a.from_json:
        with open(a.json, "w") as fh:
            json.dump(raw, fh, default=str, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
