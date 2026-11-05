#!/usr/bin/env python3
"""Download one fixture object with SigV4; credentials come from kind-secrets.env."""
import datetime
import hashlib
import hmac
from pathlib import Path
import sys
import urllib.request

host, path, destination = sys.argv[1:]
credentials = dict(line.strip().split("=", 1) for line in
                   (Path(__file__).resolve().parents[1] / "deploy/kind-secrets.env").read_text().splitlines())
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
day = now[:8]
headers = {"host": host, "x-amz-date": now, "x-amz-content-sha256": hashlib.sha256(b"").hexdigest()}
signed = ";".join(sorted(headers))
canonical = "GET\n" + path + "\n\n" + "".join(k + ":" + headers[k] + "\n" for k in sorted(headers))
canonical += "\n" + signed + "\n" + headers["x-amz-content-sha256"]
scope = day + "/us-east-1/s3/aws4_request"
key = ("AWS4" + credentials["rates-batch-s3.AWS_SECRET_ACCESS_KEY"]).encode()
for part in (day, "us-east-1", "s3", "aws4_request"):
    key = hmac.new(key, part.encode(), hashlib.sha256).digest()
to_sign = "AWS4-HMAC-SHA256\n" + now + "\n" + scope + "\n" + hashlib.sha256(canonical.encode()).hexdigest()
headers["Authorization"] = ("AWS4-HMAC-SHA256 Credential=" + credentials["rates-batch-s3.AWS_ACCESS_KEY_ID"]
                            + "/" + scope + ", SignedHeaders=" + signed + ", Signature="
                            + hmac.new(key, to_sign.encode(), hashlib.sha256).hexdigest())
with urllib.request.urlopen(urllib.request.Request("http://" + host + path, headers=headers), timeout=30) as response:
    Path(destination).write_bytes(response.read())
