#!/usr/bin/env python3
"""Replay stateful JSF requests against a target and compare with recorded responses."""

import argparse
import hashlib
import http.client
import json
import re
import sys
import time
import urllib.parse
from collections import OrderedDict
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

from record import extract_observed, portal_day_from_date_header

HERE = Path(__file__).resolve().parent
DEFAULT_BASE = "https://t-gf-before.demo.otterworks.app"


def normalize_location(location):
    if not location:
        return None
    parts = urllib.parse.urlsplit(location)
    path = re.sub(r";jsessionid=[^/?;]+", "", parts.path, flags=re.I)
    if path and not path.startswith("/"):
        path = "/" + path
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    return urllib.parse.urlunsplit(("", "", path, urllib.parse.urlencode(query), ""))


def date_spellings(day):
    if not day:
        return set()
    parsed = date.fromisoformat(day)
    return {parsed.strftime("%d.%m.%Y"), parsed.isoformat()}


def normalize_date_literals(text, recorded_on=None, replay_day=None):
    for literal in sorted(date_spellings(recorded_on) | date_spellings(replay_day), key=len, reverse=True):
        text = text.replace(literal, "<today>")
    return text


def normalize_text(text, default_period=False, strict=False, recorded_on=None, replay_day=None):
    text = re.sub(r";jsessionid=[^/?;\"']+", "", text, flags=re.I)
    text = normalize_date_literals(text, recorded_on, replay_day)
    if default_period:
        text = re.sub(r"\b20\d{2}-(?:0[1-9]|1[0-2])\b", "<default-period>", text)
    if strict:
        def normalize_viewstate(match):
            element = match.group(0)
            if re.search(r"\bname=[\"']javax\.faces\.ViewState[\"']", element, flags=re.I):
                element = re.sub(r"\bvalue=[\"'][^\"']*[\"']", 'value="<viewstate>"', element, count=1, flags=re.I)
            return element
        text = re.sub(r"<input\b[^>]*>", normalize_viewstate, text, flags=re.I)
        text = re.sub(r"j_idt\d+", "<generated-id>", text)
    return text


def normalize_observed(value, default_period=False, recorded_on=None, replay_day=None):
    if isinstance(value, dict):
        return {k: normalize_observed(v, default_period, recorded_on, replay_day) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize_observed(v, default_period, recorded_on, replay_day) for v in value]
    if isinstance(value, str):
        value = normalize_date_literals(value, recorded_on, replay_day)
        if default_period:
            value = re.sub(r"\b20\d{2}-(?:0[1-9]|1[0-2])\b", "<default-period>", value)
        if value.startswith("j_id1:javax.faces.ViewState"):
            return "<viewstate>"
    return value


class FormParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = []
        self.form = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.form = {"id": attrs.get("id"), "name": attrs.get("name"), "controls": [], "submits": []}
            self.forms.append(self.form)
        elif self.form and tag == "input":
            kind = (attrs.get("type") or "text").lower()
            control = {"type": kind, "name": attrs.get("name"), "value": attrs.get("value", "")}
            self.form["controls"].append(control)
            if kind in ("submit", "image"):
                self.form["submits"].append(control)
        elif self.form and tag == "select":
            self.form["controls"].append({"type": "select", "name": attrs.get("name")})

    def handle_endtag(self, tag):
        if tag == "form":
            self.form = None

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)


class ObservedParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.h1 = ""
        self.messages = []
        self.panels = []
        self.inputs = []
        self.tables = []
        self.stack = []
        self.table = None
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set((attrs.get("class") or "").split())
        if tag == "h1":
            self.stack.append(["h1", []])
        if tag == "div" and "panel" in classes:
            self.stack.append(["panel", []])
        if tag == "div" and classes.intersection({"err", "info"}):
            self.stack.append(["message:" + ",".join(sorted(classes.intersection({"err", "info"}))), []])
        if tag == "input":
            value = attrs.get("value", "")
            kind = (attrs.get("type") or "text").lower()
            if (attrs.get("name") or "") == "javax.faces.ViewState":
                value = "<viewstate>"
            self.inputs.append(value)
        if tag == "table":
            self.table = []
            self.tables.append(self.table)
        elif tag == "tr" and self.table is not None:
            self.row = []
            self.table.append(self.row)
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr":
            self.row = None
        elif tag == "table":
            self.table = None
        elif tag in ("h1", "div"):
            expected = "h1" if tag == "h1" else None
            for index in range(len(self.stack) - 1, -1, -1):
                kind, parts = self.stack[index]
                if (expected and kind == expected) or (tag == "div" and (kind == "panel" or kind.startswith("message:"))):
                    text = " ".join("".join(parts).split())
                    self.stack.pop(index)
                    if kind == "h1":
                        self.h1 = text
                    elif kind == "panel":
                        self.panels.append(text)
                    else:
                        self.messages.append({"class": kind.split(":", 1)[1].split(","), "text": text})
                    break

    def handle_data(self, data):
        for _, parts in self.stack:
            parts.append(data)
        if self.cell is not None:
            self.cell.append(data)


def verify_checksums():
    failures = []
    for line in (HERE / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, name = line.split(None, 1)
        name = name.strip().lstrip("*")
        actual = hashlib.sha256((HERE / name).read_bytes()).hexdigest()
        if actual != expected:
            failures.append(f"{name}: expected {expected}, got {actual}")
    return failures


def request_state(body, case_id):
    parser = FormParser()
    parser.feed(body)
    if not parser.forms:
        raise RuntimeError(f"{case_id}: previous response has no form")
    form = parser.forms[0]
    form_name = form.get("name") or form.get("id")
    state = re.search(
        r'<input\b[^>]*name=["\']javax\.faces.ViewState["\'][^>]*value=["\']([^"\']*)["\']',
        body,
        flags=re.I,
    ) or re.search(
        r'<input\b[^>]*value=["\']([^"\']*)["\'][^>]*name=["\']javax\.faces.ViewState["\']',
        body,
        flags=re.I,
    )
    if not form_name or not state:
        raise RuntimeError(f"{case_id}: missing generated form name or ViewState")
    fields = {}
    ordinals = {"text": 0, "radio": 0, "checkbox": 0}
    select_ordinal = 0
    for control in form["controls"]:
        kind = control["type"]
        if kind == "text":
            fields[f"text:{ordinals['text']}"] = control["name"]
            ordinals["text"] += 1
        elif kind in ("radio", "checkbox"):
            fields[f"{kind}:{ordinals[kind]}"] = control["name"]
            ordinals[kind] += 1
        elif kind == "select":
            fields[f"select:{select_ordinal}"] = control["name"]
            select_ordinal += 1
    return {
        "formName": form_name,
        "viewState": state.group(1),
        "fields": fields,
        "submits": {item["value"]: item["name"] for item in form["submits"]},
    }


def fetch(base, case, cookies, previous_html, previous_location, timeout):
    path = previous_location if case.get("followPreviousLocation") else case.get("path")
    if not path:
        raise RuntimeError(f"{case['id']}: previous response has no Location")
    parts = urllib.parse.urlsplit(base)
    target = urllib.parse.urlsplit(path)
    request_path = target.path or "/"
    if target.query:
        request_path += "?" + target.query
    headers = {"Accept": "text/html,*/*"}
    if cookies:
        headers["Cookie"] = "; ".join(f"{key}={value}" for key, value in cookies.items())
    body = None
    if case["method"] == "POST":
        form = case["form"]
        state = request_state(previous_html, case["id"])
        pairs = [(state["formName"], state["formName"]),
                 ("javax.faces.ViewState", state["viewState"])]
        for selector, value in form.get("fields", {}).items():
            if selector not in state["fields"]:
                raise RuntimeError(f"{case['id']}: field selector {selector!r} not found in previous response")
            pairs.append((state["fields"][selector], value))
        if form["submit"] not in state["submits"]:
            raise RuntimeError(f"{case['id']}: submit control {form['submit']!r} not found in previous response")
        pairs.append((state["submits"][form["submit"]], form["submit"]))
        body = urllib.parse.urlencode(pairs).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    conn_cls = http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(parts.hostname, parts.port, timeout=timeout)
    started = time.monotonic()
    try:
        conn.request(case["method"], request_path, body=body, headers=headers)
        response = conn.getresponse()
        raw = response.read()
        status = response.status
        media_type = (response.getheader("Content-Type") or "").split(";", 1)[0].strip().lower() or None
        location = normalize_location(response.getheader("Location"))
        replay_day = portal_day_from_date_header(response.getheader("Date"))
        for cookie in response.headers.get_all("Set-Cookie") or []:
            match = re.match(r"\s*([^=;]+)=([^;]*)", cookie)
            if match:
                cookies[match.group(1)] = match.group(2)
    finally:
        conn.close()
    body_text = raw.decode("utf-8", errors="replace")
    return {
        "status": status,
        "mediaType": media_type,
        "location": location,
        "body": body_text,
        "observed": extract_observed(body_text),
        "replayDay": replay_day,
        "elapsedMs": round((time.monotonic() - started) * 1000),
    }, body_text


def compare(expected, actual, case, strict, recorded_on=None, replay_day=None):
    problems = []
    replay_day = replay_day or actual.get("replayDay")
    for key in ("status", "location", "mediaType"):
        if expected.get(key) != actual.get(key):
            problems.append(f"{key}: {expected.get(key)!r} != {actual.get(key)!r}")
    default_period = case.get("normalizeDefaultPeriod", False)
    expected_observed = normalize_observed(
        extract_observed(expected["body"]), default_period, recorded_on, replay_day
    )
    actual_observed = normalize_observed(
        extract_observed(actual["body"]), default_period, recorded_on, replay_day
    )
    if expected_observed != actual_observed:
        problems.append("observed block differs")
    if expected.get("mediaType") != "text/html" or actual.get("mediaType") != "text/html":
        before = normalize_text(expected["body"], default_period, recorded_on=recorded_on, replay_day=replay_day)
        after = normalize_text(actual["body"], default_period, recorded_on=recorded_on, replay_day=replay_day)
        if before != after:
            problems.append("normalised non-HTML body differs")
    elif strict:
        before = normalize_text(
            expected["body"], default_period, strict=True, recorded_on=recorded_on, replay_day=replay_day
        )
        after = normalize_text(
            actual["body"], default_period, strict=True, recorded_on=recorded_on, replay_day=replay_day
        )
        if before != after:
            problems.append("normalised raw body differs")
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--stage", choices=("first", "full"), required=True)
    parser.add_argument("--out", required=True, help="directory for per-context JSON and SUMMARY.md")
    parser.add_argument("--strict", action="store_true", help="also compare normalised raw bodies")
    parser.add_argument("--replay-day", help="override the replay day (YYYY-MM-DD)")
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    if args.replay_day:
        try:
            if date.fromisoformat(args.replay_day).isoformat() != args.replay_day:
                raise ValueError
        except ValueError:
            parser.error("--replay-day must be a valid YYYY-MM-DD date")
    failures = verify_checksums()
    if failures:
        for failure in failures:
            print(f"checksum mismatch: {failure}", file=sys.stderr)
        return 1
    corpus = json.loads((HERE / "requests.json").read_text(encoding="utf-8"))
    recorded = json.loads((HERE / "recorded.json").read_text(encoding="utf-8"))
    expected_by_id = {entry["id"]: entry["response"] for entries in recorded["contexts"].values() for entry in entries}
    contexts = OrderedDict()
    for case in corpus["cases"]:
        contexts.setdefault(case["context"], []).append(case)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for context, cases in contexts.items():
        cookies = {}
        previous_html = ""
        previous_location = None
        rows = []
        for case in cases:
            actual, previous_html = fetch(args.base, case, cookies, previous_html, previous_location, args.timeout)
            previous_location = actual["location"]
            problems = compare(
                expected_by_id[case["id"]], actual, case, args.strict,
                recorded_on=recorded["recordedOn"],
                replay_day=args.replay_day or actual["replayDay"],
            )
            rows.append({"id": case["id"], "status": actual["status"], "mediaType": actual["mediaType"],
                         "location": actual["location"], "problems": problems, "actual": actual})
            print(f"{context}/{case['id']}: {'IDENTICAL' if not problems else 'DIFFERENT'}")
            if problems and args.stage == "first":
                break
        different = sum(bool(row["problems"]) for row in rows)
        result = {"context": context, "casesInCorpus": len(cases), "casesRun": len(rows),
                  "identical": len(rows) - different, "different": different,
                  "status": "identical" if not different else "different", "cases": rows}
        (out / f"{context}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        results.append(result)
    total_cases = sum(result["casesRun"] for result in results)
    total_identical = sum(result["identical"] for result in results)
    total_different = sum(result["different"] for result in results)
    lines = [
        "# JSF replay summary", "",
        f"- Target: `{args.base}`",
        f"- Stage: `{args.stage}`",
        f"- Strict raw-body comparison: `{'yes' if args.strict else 'no'}`",
        f"- Cases: **{total_identical}/{total_cases} identical**; **{total_different} different**",
        "", "| Context | Cases in corpus | Cases run | Identical | Different | Result |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for result in results:
        lines.append(f"| {result['context']} | {result['casesInCorpus']} | {result['casesRun']} | "
                     f"{result['identical']} | {result['different']} | {result['status']} |")
    lines += ["", "Per-context details are in the adjacent JSON files."]
    (out / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if total_different == 0 and total_cases == len(corpus["cases"]) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"replay failed: {exc}", file=sys.stderr)
        sys.exit(1)
