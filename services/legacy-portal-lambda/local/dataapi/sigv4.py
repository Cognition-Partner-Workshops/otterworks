"""AWS Signature Version 4 verification for the local Data API.

The handlers' SDK signs every ExecuteStatement call with the credentials it resolves. The stack
gives the functions and this server one random key pair per run (see the certs service), so a
request that is unsigned, signed with another key, altered after signing or replayed outside the
clock window is refused before any SQL is looked at.
"""
import configparser
import datetime as dt
import hashlib
import hmac
import re
import urllib.parse

ALGORITHM = "AWS4-HMAC-SHA256"
MAX_SKEW = dt.timedelta(minutes=15)
AUTH = re.compile(r"^AWS4-HMAC-SHA256 Credential=([^/,\s]+)/(\d{8})/([^/,\s]+)/([^/,\s]+)/aws4_request,"
                  r"\s*SignedHeaders=([a-z0-9;\-]+),\s*Signature=([0-9a-f]{64})$")


class AuthError(Exception):
    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind


def load_credentials(path, profile="default"):
    parser = configparser.ConfigParser()
    if not parser.read(path) or not parser.has_section(profile):
        raise SystemExit(f"no [{profile}] credentials in {path}")
    key_id = parser.get(profile, "aws_access_key_id", fallback="")
    secret = parser.get(profile, "aws_secret_access_key", fallback="")
    if len(key_id) < 16 or len(secret) < 32:
        raise SystemExit(f"{path}: per-run credentials are missing or too short")
    return key_id, secret


def _hmac(key, msg):
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def signing_key(secret, date, region, service):
    return _hmac(_hmac(_hmac(_hmac(("AWS4" + secret).encode(), date), region), service), "aws4_request")


def _canonical_query(query):
    pairs = urllib.parse.parse_qsl(query, keep_blank_values=True)
    enc = lambda s: urllib.parse.quote(s, safe="-_.~")
    return "&".join(f"{enc(k)}={enc(v)}" for k, v in sorted(pairs))


def canonical_request(method, path, query, headers, signed, payload_hash):
    uri = urllib.parse.quote(path or "/", safe="/-_.~")
    lines = "".join(f"{h}:{' '.join((headers.get(h) or '').split())}\n" for h in signed)
    return "\n".join([method, uri, _canonical_query(query), lines, ";".join(signed), payload_hash])


def verify(method, target, headers, body, key_id, secret, now=None):
    """Raise AuthError unless the request carries a valid SigV4 signature by key_id/secret.

    headers must be a case-insensitive mapping (http.server's message object or a lower-cased dict).
    """
    auth = headers.get("authorization")
    if not auth:
        raise AuthError("MissingAuthenticationTokenException", "request is not signed")
    m = AUTH.match(auth.strip())
    if not m:
        raise AuthError("IncompleteSignatureException", "malformed Authorization header")
    akid, date, region, service, signed_raw, signature = m.groups()
    if not hmac.compare_digest(akid, key_id):
        raise AuthError("UnrecognizedClientException", "unknown access key")
    signed = signed_raw.split(";")
    if signed != sorted(signed) or "host" not in signed or "x-amz-date" not in signed:
        raise AuthError("IncompleteSignatureException", "host and x-amz-date must be signed")
    amz_date = headers.get("x-amz-date") or ""
    try:
        stamp = dt.datetime.strptime(amz_date, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        raise AuthError("IncompleteSignatureException", "bad x-amz-date") from None
    if amz_date[:8] != date:
        raise AuthError("InvalidSignatureException", "credential scope date does not match x-amz-date")
    now = now or dt.datetime.now(dt.timezone.utc)
    if abs(now - stamp) > MAX_SKEW:
        raise AuthError("InvalidSignatureException", "signature expired or not yet valid")
    payload_hash = hashlib.sha256(body).hexdigest()
    claimed = headers.get("x-amz-content-sha256")
    if claimed and claimed != payload_hash:
        raise AuthError("InvalidSignatureException", "payload does not match x-amz-content-sha256")
    path, _, query = target.partition("?")
    creq = canonical_request(method, path, query, headers, signed, payload_hash)
    scope = f"{date}/{region}/{service}/aws4_request"
    to_sign = "\n".join([ALGORITHM, amz_date, scope, hashlib.sha256(creq.encode()).hexdigest()])
    expected = hmac.new(signing_key(secret, date, region, service), to_sign.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise AuthError("InvalidSignatureException", "signature does not match")
