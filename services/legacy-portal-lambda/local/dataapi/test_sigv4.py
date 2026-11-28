import datetime as dt
import hashlib
import hmac
import os
import tempfile
import unittest

import sigv4

KEY_ID = "LPLOCALTESTKEY000001"
SECRET = "test-secret-not-used-anywhere-0123456789"
NOW = dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt.timezone.utc)
BODY = b'{"sql":"SELECT 1"}'


def signed_headers(body=BODY, key_id=KEY_ID, secret=SECRET, when=NOW, host="dataapi:8080"):
    amz_date = when.strftime("%Y%m%dT%H%M%SZ")
    headers = {"host": host, "x-amz-date": amz_date, "content-type": "application/json"}
    signed = ["content-type", "host", "x-amz-date"]
    creq = sigv4.canonical_request("POST", "/Execute", "", headers, signed, hashlib.sha256(body).hexdigest())
    scope = f"{amz_date[:8]}/us-east-1/rds-data/aws4_request"
    to_sign = "\n".join([sigv4.ALGORITHM, amz_date, scope, hashlib.sha256(creq.encode()).hexdigest()])
    sig = hmac.new(sigv4.signing_key(secret, amz_date[:8], "us-east-1", "rds-data"), to_sign.encode(),
                   hashlib.sha256).hexdigest()
    headers["authorization"] = (f"{sigv4.ALGORITHM} Credential={key_id}/{scope}, "
                                f"SignedHeaders={';'.join(signed)}, Signature={sig}")
    return headers


class VerifyTest(unittest.TestCase):
    def check(self, headers, body=BODY, kind=None):
        call = lambda: sigv4.verify("POST", "/Execute", headers, body, KEY_ID, SECRET, now=NOW)
        if kind is None:
            call()
        else:
            with self.assertRaises(sigv4.AuthError) as ctx:
                call()
            self.assertEqual(ctx.exception.kind, kind)

    def test_signing_key_matches_aws_example(self):
        # "Examples of how to derive a signing key for Signature Version 4" in the AWS docs.
        key = sigv4.signing_key("wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY", "20150830", "us-east-1", "iam")
        self.assertEqual(key.hex(), "c4afb1cc5771d871763a393e44b703571b55cc28424d1a5e86da6ed3c154a4b9")

    def test_valid_request_is_accepted(self):
        self.check(signed_headers())

    def test_missing_credentials_are_denied(self):
        headers = signed_headers()
        del headers["authorization"]
        self.check(headers, kind="MissingAuthenticationTokenException")

    def test_malformed_header_is_denied(self):
        self.check({**signed_headers(), "authorization": "Bearer x"}, kind="IncompleteSignatureException")

    def test_unknown_key_is_denied(self):
        self.check(signed_headers(key_id="LPLOCALOTHERKEY00002"), kind="UnrecognizedClientException")

    def test_wrong_secret_is_denied(self):
        self.check(signed_headers(secret="another-secret-0123456789abcdef0123"), kind="InvalidSignatureException")

    def test_altered_body_is_denied(self):
        self.check(signed_headers(), body=b'{"sql":"SELECT 2"}', kind="InvalidSignatureException")

    def test_altered_signed_header_is_denied(self):
        self.check({**signed_headers(), "host": "elsewhere:8080"}, kind="InvalidSignatureException")

    def test_stale_signature_is_denied(self):
        self.check(signed_headers(when=NOW - dt.timedelta(minutes=16)), kind="InvalidSignatureException")

    def test_unsigned_host_is_denied(self):
        headers = signed_headers()
        headers["authorization"] = headers["authorization"].replace("content-type;host;x-amz-date", "x-amz-date")
        self.check(headers, kind="IncompleteSignatureException")


class CredentialsTest(unittest.TestCase):
    def write(self, text):
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, "w") as f:
            f.write(text)
        self.addCleanup(os.remove, path)
        return path

    def test_missing_file_fails_closed(self):
        with self.assertRaises(SystemExit):
            sigv4.load_credentials("/nonexistent/credentials")

    def test_short_credentials_fail_closed(self):
        with self.assertRaises(SystemExit):
            sigv4.load_credentials(self.write("[default]\naws_access_key_id=local\naws_secret_access_key=local\n"))

    def test_reads_default_profile(self):
        path = self.write(f"[default]\naws_access_key_id={KEY_ID}\naws_secret_access_key={SECRET}\n")
        self.assertEqual(sigv4.load_credentials(path), (KEY_ID, SECRET))


if __name__ == "__main__":
    unittest.main()
