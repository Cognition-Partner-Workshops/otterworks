"""Send Grafana-compatible pipeline notifications, or print a dry-run payload."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from checks import MODEL, RUN, add_arguments, run_checks, thresholds


def payload(result, now=None):
    now = now or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    common = {"run": RUN, "model": MODEL, "severity": "critical",
              "pipeline": RUN, "team": "otterworks"}
    alerts = []
    for name, check in result["checks"].items():
        if not check["firing"]:
            continue
        labels = {**common, "alertname": "SfxPipeline_" + name, "check": name}
        description = (f"day={check['day']} file={check['file']} "
                       f"value={check['value']} threshold={check['threshold']}")
        alerts.append({"status": "firing", "labels": labels,
                       "annotations": {"summary": f"Pipeline {name} firing", "description": description},
                       "values": {"A": check["value"], "threshold": check["threshold"]},
                       "startsAt": now, "endsAt": "0001-01-01T00:00:00Z",
                       "generatorURL": "", "fingerprint": hashlib.sha256(
                           json.dumps(labels, sort_keys=True).encode()).hexdigest()[:16]})
    firing = bool(alerts)
    message = f"{len(alerts)} pipeline checks firing" if firing else "All pipeline checks green"
    return {"receiver": "devin-pipeline-webhook", "status": "firing" if firing else "resolved",
            "orgId": 1, "alerts": alerts, "groupLabels": {"pipeline": RUN},
            "commonLabels": common, "commonAnnotations": {}, "externalURL": "http://localhost:3001/",
            "version": "1", "groupKey": '{}:{pipeline="sfx-d1110"}', "truncatedAlerts": 0,
            "title": message, "state": "alerting" if firing else "ok", "message": message}


class RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never replay a bearer credential to a redirect destination.
        return None


def open_webhook(request, timeout):
    return build_opener(RejectRedirects()).open(request, timeout=timeout)


def deliver(body, url=None, secret=None, opener=open_webhook):
    url = os.getenv("DEVIN_PIPELINE_WEBHOOK_URL", "") if url is None else url
    if not url or not body["alerts"]:
        print(json.dumps(body, indent=2))
        return 0
    try:
        target = urlsplit(url)
        if (target.scheme != "https" or not target.hostname
                or target.username is not None or target.password is not None
                or target.fragment or any(ord(char) <= 32 or ord(char) == 127 for char in url)):
            raise ValueError("Invalid webhook URL")
        # Accessing port also validates numeric syntax and its range.
        target.port
    except ValueError:
        print("Webhook URL must use HTTPS without credentials or a fragment", file=sys.stderr)
        return 1
    secret = os.getenv("DEVIN_PIPELINE_WEBHOOK_SECRET", "") if secret is None else secret
    if not secret:
        print("Webhook secret is required when URL is set", file=sys.stderr)
        return 1
    try:
        request = Request(url, data=json.dumps(body).encode(), method="POST",
                          headers={"Content-Type": "application/json", "Authorization": "Bearer " + secret})
        with opener(request, timeout=30) as response:
            if not 200 <= response.status < 300:
                print(f"Webhook HTTP failure: {response.status}", file=sys.stderr)
                return 1
        print("Pipeline notification sent")
        return 0
    except (HTTPError, URLError, TimeoutError, ValueError):
        print("Webhook HTTP request failed", file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser()
    add_arguments(parser)
    return deliver(payload(run_checks(thresholds(parser.parse_args()))))


if __name__ == "__main__":
    sys.exit(main())
