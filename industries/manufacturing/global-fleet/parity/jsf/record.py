#!/usr/bin/env python3
"""Capture the ordered JSF portal corpus using an independent cookie jar per context."""

import argparse
import hashlib
import http.client
import json
import re
import sys
import time
import urllib.parse
from collections import OrderedDict
from datetime import timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
DEFAULT_BASE = "https://t-gf-before.demo.otterworks.app"
PORTAL_TIMEZONE = "Etc/UTC"


def text_value(parts):
    return " ".join("".join(parts).split())


def portal_day_from_date_header(value):
    if not value:
        raise ValueError("response has no HTTP Date header")
    parsed = parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(ZoneInfo(PORTAL_TIMEZONE)).date().isoformat()


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = []
        self.form = None
        self.inputs = []
        self.selects = []
        self.radios = []
        self._captures = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.form = {"id": attrs.get("id"), "name": attrs.get("name"), "action": attrs.get("action"),
                         "controls": [], "submits": []}
            self.forms.append(self.form)
        elif self.form and tag == "input":
            kind = (attrs.get("type") or "text").lower()
            item = {"type": kind, "name": attrs.get("name"), "value": attrs.get("value", "")}
            self.form["controls"].append(item)
            if kind in ("submit", "image"):
                self.form["submits"].append(item)
        elif self.form and tag == "select":
            item = {"name": attrs.get("name"), "value": None}
            self.form["controls"].append({"type": "select", **item})
            self.selects.append(item)
        if tag == "input":
            self.inputs.append({"type": (attrs.get("type") or "text").lower(), "value": attrs.get("value", "")})
        if tag in ("h1", "div", "td", "th", "tr", "table"):
            classes = set((attrs.get("class") or "").split())
            if tag == "h1" or (tag == "div" and "panel" in classes):
                self._captures.append({"kind": "h1" if tag == "h1" else "panel", "tag": tag, "parts": []})

    def handle_endtag(self, tag):
        if self.form and tag == "form":
            self.form = None
        for i in range(len(self._captures) - 1, -1, -1):
            capture = self._captures[i]
            if capture["tag"] == tag:
                capture["text"] = text_value(capture["parts"])
                self._captures.pop(i)
                if capture["kind"] == "h1":
                    self.h1 = capture["text"]
                else:
                    self.panels.append(capture["text"])

    def handle_data(self, data):
        for capture in self._captures:
            capture["parts"].append(data)

    h1 = ""
    panels = []

    def observed(self, body):
        self.h1 = ""
        self.panels = []
        self.tables = []
        self.messages = []
        self._captures = []
        self.forms = []
        self.form = None
        self.inputs = []
        self.selects = []
        self.feed(body)
        return {
            "h1": self.h1,
            "messages": self.messages,
            "tables": self.tables,
            "panels": self.panels,
            "inputs": [item["value"] for item in self.inputs],
        }

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)


class ObservationParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.h1 = ""
        self.messages = []
        self.panels = []
        self.inputs = []
        self.tables = []
        self.captures = []
        self.table = None
        self.row = None
        self.cell = None
        self.visible_parts = []
        self.ignored_tag = None
        self.in_body = False

    def handle_starttag(self, tag, attrs):
        if self.ignored_tag:
            return
        if tag in ("script", "style"):
            self.ignored_tag = tag
            return
        if tag == "body":
            self.in_body = True
        attrs = dict(attrs)
        classes = set((attrs.get("class") or "").split())
        if tag == "h1":
            self.captures.append({"kind": "h1", "tag": tag, "parts": []})
        elif tag == "div" and "panel" in classes:
            self.captures.append({"kind": "panel", "tag": tag, "parts": []})
        elif classes.intersection({"err", "info"}):
            self.captures.append({"kind": "message", "tag": tag,
                                  "classes": sorted(classes.intersection({"err", "info"})), "parts": []})
        if tag == "input":
            kind = (attrs.get("type") or "text").lower()
            value = attrs.get("value", "")
            if (attrs.get("name") or "") == "javax.faces.ViewState":
                value = "<viewstate>"
            self.inputs.append({"type": kind, "value": value})
        if tag == "table":
            self.table = []
            self.tables.append(self.table)
        elif tag == "tr" and self.table is not None:
            self.row = []
            self.table.append(self.row)
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_endtag(self, tag):
        if self.ignored_tag:
            if tag == self.ignored_tag:
                self.ignored_tag = None
            return
        if tag == "body":
            self.in_body = False
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(text_value(self.cell))
            self.cell = None
        elif tag == "tr":
            self.row = None
        elif tag == "table":
            self.table = None
        for index in range(len(self.captures) - 1, -1, -1):
            capture = self.captures[index]
            if capture["tag"] == tag:
                self.captures.pop(index)
                text = text_value(capture["parts"])
                if capture["kind"] == "h1":
                    self.h1 = text
                elif capture["kind"] == "panel":
                    self.panels.append(text)
                else:
                    self.messages.append({"class": capture["classes"], "text": text})
                break

    def handle_data(self, data):
        if self.ignored_tag or not self.in_body:
            return
        self.visible_parts.append(data)
        for capture in self.captures:
            capture["parts"].append(data)
        if self.cell is not None:
            self.cell.append(data)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)


def extract_observed(body):
    parser = ObservationParser()
    parser.feed(body)
    visible_text = text_value(parser.visible_parts)
    visible_text = re.sub(r"\b(?:j_idt?\d+:)?javax\.faces\.ViewState\b", "", visible_text)
    visible_text = re.sub(r"\bj_idt?\d+\b", "", visible_text)
    return {"h1": parser.h1, "messages": parser.messages, "tables": parser.tables,
            "panels": parser.panels, "inputs": parser.inputs, "text": text_value([visible_text])}


def normalize_location(location):
    if not location:
        return None
    parts = urllib.parse.urlsplit(location)
    path = re.sub(r";jsessionid=[^/?;]+", "", parts.path, flags=re.I)
    if path and not path.startswith("/"):
        path = "/" + path
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    return urllib.parse.urlunsplit(("", "", path, urllib.parse.urlencode(query), ""))


def send(base, case, cookies, previous_location, timeout):
    path = previous_location if case.get("followPreviousLocation") else case["path"]
    if not path:
        raise RuntimeError(f"{case['id']}: previous response has no Location")
    base_parts = urllib.parse.urlsplit(base)
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
        # The caller attaches the previous HTML and the extracted live form fields.
        form_state = case["_formState"]
        pairs = [(form_state["formName"], form_state["formName"]),
                 ("javax.faces.ViewState", form_state["viewState"])]
        for selector, value in form.get("fields", {}).items():
            pairs.append((form_state["fields"][selector], value))
        submit_name = form_state["submits"].get(form["submit"])
        if submit_name is None:
            raise RuntimeError(f"{case['id']}: submit control {form['submit']!r} not found")
        pairs.append((submit_name, form["submit"]))
        body = urllib.parse.urlencode(pairs).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    conn_cls = http.client.HTTPSConnection if base_parts.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(base_parts.hostname, base_parts.port, timeout=timeout)
    started = time.monotonic()
    try:
        conn.request(case["method"], request_path, body=body, headers=headers)
        response = conn.getresponse()
        raw = response.read()
        status = response.status
        media_type = (response.getheader("Content-Type") or "").split(";", 1)[0].strip().lower() or None
        raw_location = response.getheader("Location")
        date_header = response.getheader("Date")
        for cookie in response.headers.get_all("Set-Cookie") or []:
            match = re.match(r"\s*([^=;]+)=([^;]*)", cookie)
            if match:
                cookies[match.group(1)] = match.group(2)
    finally:
        conn.close()
    elapsed_ms = round((time.monotonic() - started) * 1000)
    body_text = raw.decode("utf-8", errors="replace")
    parsed = extract_observed(body_text)
    return {
        "status": status,
        "mediaType": media_type,
        "location": normalize_location(raw_location),
        "body": body_text,
        "observed": parsed,
        "elapsedMs": elapsed_ms,
    }, body_text, date_header


def state_for_post(body, form_spec, case_id):
    parser = PageParser()
    parser.observed(body)
    if not parser.forms:
        raise RuntimeError(f"{case_id}: previous response has no form")
    form = parser.forms[0]
    form_name = form.get("name") or form.get("id")
    state_match = re.search(
        r'<input\b[^>]*name=["\']javax\.faces\.ViewState["\'][^>]*value=["\']([^"\']*)["\']',
        body,
        flags=re.I,
    )
    if not state_match:
        state_match = re.search(
            r'<input\b[^>]*value=["\']([^"\']*)["\'][^>]*name=["\']javax\.faces\.ViewState["\']',
            body,
            flags=re.I,
        )
    if not form_name or not state_match:
        raise RuntimeError(f"{case_id}: missing generated form name or ViewState")
    controls = form["controls"]
    fields = {}
    input_ordinals = {"text": 0, "radio": 0, "checkbox": 0}
    select_ordinal = 0
    for control in controls:
        kind = control["type"]
        if kind in ("text", "radio", "checkbox", "password", "hidden"):
            selector_kind = "text" if kind == "text" else kind
            if selector_kind in input_ordinals and kind != "hidden":
                key = f"{selector_kind}:{input_ordinals[selector_kind]}"
                fields[key] = control["name"]
                input_ordinals[selector_kind] += 1
        elif kind == "select":
            fields[f"select:{select_ordinal}"] = control["name"]
            select_ordinal += 1
    view_match = state_match.group(1)
    submits = {item["value"]: item["name"] for item in form["submits"]}
    return {"formName": form_name, "viewState": view_match, "fields": fields, "submits": submits}


def checksum_files():
    names = ["requests.json", "recorded.json"]
    lines = []
    for name in names:
        digest = hashlib.sha256((HERE / name).read_bytes()).hexdigest()
        lines.append(f"{digest}  {name}")
    (HERE / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    corpus = json.loads((HERE / "requests.json").read_text(encoding="utf-8"))
    cases_by_context = OrderedDict()
    for case in corpus["cases"]:
        cases_by_context.setdefault(case["context"], []).append(case)
    recorded = {"base": args.base, "contexts": {}}
    for context, cases in cases_by_context.items():
        cookies = {}
        previous_html = ""
        previous_location = None
        entries = []
        for case in cases:
            case_copy = dict(case)
            if case.get("method") == "POST":
                case_copy["_formState"] = state_for_post(previous_html, case["form"], case["id"])
            response, previous_html, date_header = send(
                args.base, case_copy, cookies, previous_location, args.timeout
            )
            if "recordedOn" not in recorded:
                recorded["recordedOn"] = portal_day_from_date_header(date_header)
            previous_location = response["location"]
            entries.append({"id": case["id"], "response": response})
            print(f"{context}/{case['id']}: {response['status']} {response['mediaType'] or '-'} "
                  f"{response['location'] or ''}")
        recorded["contexts"][context] = entries
    (HERE / "recorded.json").write_text(json.dumps(recorded, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    checksum_files()
    print(f"recorded {sum(map(len, recorded['contexts'].values()))} cases in {len(recorded['contexts'])} contexts")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"recording failed: {exc}", file=sys.stderr)
        sys.exit(1)
