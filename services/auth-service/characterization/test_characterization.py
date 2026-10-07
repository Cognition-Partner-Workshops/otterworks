"""Characterization tests for auth-service, run against a RUNNING instance over HTTP.

They pin the behavior observed on the pre-upgrade code (Java 17 / Spring Boot 3.2.4),
including odd behavior, so the same file can be rerun unchanged after an upgrade.

  AUTH_BASE_URL   base URL of the running service (default http://localhost:8081)
  AUTH_JWT_SECRET JWT signing secret the instance runs with; used only to mint an
                  ADMIN-role access token for the admin-only endpoint
                  (default: the docker-compose dev secret)

Run: python3 characterization/test_characterization.py   (stdlib only, Python 3.8+)
"""

import base64
import hashlib
import hmac
import json
import os
import re
import sys
import time
import unittest
import urllib.error
import urllib.request
import uuid

BASE = os.environ.get("AUTH_BASE_URL", "http://localhost:8081").rstrip("/")
JWT_SECRET = os.environ.get(
    "AUTH_JWT_SECRET", "otterworks-local-dev-jwt-secret-change-me-in-production"
)
RUN_ID = uuid.uuid4().hex[:10]
SEED_ADMIN_ID = "a0000000-0000-0000-0000-000000000001"
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,9})?Z$")
ERROR_KEYS = ["timestamp", "status", "error", "message"]
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-XSS-Protection": "0",
    "Cache-Control": "no-cache, no-store, max-age=0, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
    "X-Frame-Options": "DENY",
}


class Resp:
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = headers
        self.raw = body
        self.text = body.decode("utf-8", "replace")

    def json(self):
        return json.loads(self.text)

    def header(self, name):
        return self.headers.get(name)


def call(method, path, body=None, token=None, raw_body=None, headers=None):
    hdrs = dict(headers or {})
    data = None
    if raw_body is not None:
        data = raw_body.encode()
        hdrs.setdefault("Content-Type", "application/json")
    elif body is not None:
        data = json.dumps(body).encode()
        hdrs.setdefault("Content-Type", "application/json")
    if token:
        hdrs["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return Resp(r.status, r.headers, r.read())
    except urllib.error.HTTPError as e:
        return Resp(e.code, e.headers, e.read())


def b64url_decode(seg):
    return base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4))


def jwt_parts(token):
    h, p, _ = token.split(".")
    return json.loads(b64url_decode(h)), json.loads(b64url_decode(p))


def mint_hs384(claims):
    def enc(obj):
        return base64.urlsafe_b64encode(json.dumps(obj, separators=(",", ":")).encode()).rstrip(b"=")

    signing_input = enc({"alg": "HS384"}) + b"." + enc(claims)
    sig = hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha384).digest()
    return (signing_input + b"." + base64.urlsafe_b64encode(sig).rstrip(b"=")).decode()


def email(tag):
    return "char-%s-%s@otterworks.test" % (tag, RUN_ID)


def register(tag, password="password123", display="Char User"):
    r = call("POST", "/api/v1/auth/register",
             {"email": email(tag), "password": password, "displayName": display})
    assert r.status == 201, (r.status, r.text)
    return r.json()


class CharacterizationBase(unittest.TestCase):
    maxDiff = None

    def assertError(self, r, status, error, message):
        self.assertEqual(r.status, status, r.text)
        self.assertEqual(r.header("Content-Type"), "application/json")
        b = r.json()
        self.assertEqual(list(b.keys()), ERROR_KEYS)
        self.assertRegex(b["timestamp"], ISO_RE)
        self.assertEqual(b["status"], status)
        self.assertEqual(b["error"], error)
        self.assertEqual(b["message"], message)

    def assertEmpty403(self, r):
        self.assertEqual(r.status, 403, r.text)
        self.assertEqual(r.raw, b"")
        self.assertEqual(r.header("Content-Length"), "0")

    def assertSecurityHeaders(self, r):
        for k, v in SECURITY_HEADERS.items():
            self.assertEqual(r.header(k), v, k)


class T01Health(CharacterizationBase):
    def test_health_ok_body_and_headers(self):
        r = call("GET", "/health")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.header("Content-Type"), "application/json")
        self.assertEqual(r.text, '{"service":"auth-service","status":"healthy","database":{"status":"up"}}')
        self.assertSecurityHeaders(r)

    def test_health_is_public_even_with_garbage_token(self):
        r = call("GET", "/health", token="not-a-jwt")
        self.assertEqual(r.status, 200)


class T02Actuator(CharacterizationBase):
    def test_metrics_prometheus_text(self):
        r = call("GET", "/metrics")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.header("Content-Type"), "text/plain;version=0.0.4;charset=utf-8")
        for name in ["jvm_memory_used_bytes", "http_server_requests_seconds_count",
                     "hikaricp_connections_active", "process_uptime_seconds"]:
            self.assertRegex(r.text, r"(?m)^%s\{" % name, name)
        self.assertIn('application="auth-service"', r.text)

    def test_info_is_not_permitted_403(self):
        self.assertEmpty403(call("GET", "/info"))

    def test_actuator_paths_not_exposed_500(self):
        # base-path is "/", so /actuator/* do not exist; permitAll + generic handler -> 500
        for p in ["/actuator/health", "/actuator/info", "/actuator/prometheus"]:
            self.assertError(call("GET", p), 500, "Internal Server Error", "Internal server error")

    def test_unknown_public_path_403(self):
        self.assertEmpty403(call("GET", "/does-not-exist"))


class T03Register(CharacterizationBase):
    def test_register_created_shape_and_tokens(self):
        r = call("POST", "/api/v1/auth/register",
                 {"email": email("reg"), "password": "password123", "displayName": "Reg User"})
        self.assertEqual(r.status, 201, r.text)
        self.assertEqual(r.header("Content-Type"), "application/json")
        self.assertSecurityHeaders(r)
        b = r.json()
        self.assertEqual(list(b.keys()), ["accessToken", "refreshToken", "tokenType", "expiresIn", "user"])
        self.assertEqual(b["tokenType"], "Bearer")
        self.assertEqual(b["expiresIn"], 3600)
        self.assertEqual(list(b["user"].keys()), ["id", "email", "displayName", "avatarUrl"])
        self.assertRegex(b["user"]["id"], UUID_RE)
        self.assertEqual(b["user"]["email"], email("reg"))
        self.assertEqual(b["user"]["displayName"], "Reg User")
        self.assertIsNone(b["user"]["avatarUrl"])

        h, p = jwt_parts(b["accessToken"])
        self.assertEqual(h, {"alg": "HS384"})
        self.assertEqual(list(p.keys()), ["sub", "email", "name", "roles", "type", "iat", "exp"])
        self.assertEqual(p["sub"], b["user"]["id"])
        self.assertEqual(p["email"], email("reg"))
        self.assertEqual(p["name"], "Reg User")
        self.assertEqual(p["roles"], ["USER"])
        self.assertEqual(p["type"], "access")
        self.assertEqual(p["exp"] - p["iat"], 3600)

        h, p = jwt_parts(b["refreshToken"])
        self.assertEqual(h, {"alg": "HS384"})
        self.assertEqual(list(p.keys()), ["sub", "jti", "type", "iat", "exp"])
        self.assertEqual(p["sub"], b["user"]["id"])
        self.assertRegex(p["jti"], UUID_RE)
        self.assertEqual(p["type"], "refresh")
        self.assertEqual(p["exp"] - p["iat"], 2592000)

    def test_register_duplicate_email_400(self):
        register("dup")
        r = call("POST", "/api/v1/auth/register",
                 {"email": email("dup"), "password": "password123", "displayName": "Again"})
        self.assertError(r, 400, "Bad Request", "Email already registered")

    def test_register_invalid_email_400(self):
        r = call("POST", "/api/v1/auth/register",
                 {"email": "not-an-email", "password": "password123", "displayName": "X"})
        self.assertError(r, 400, "Bad Request", "email: must be a well-formed email address")

    def test_register_short_password_400(self):
        r = call("POST", "/api/v1/auth/register",
                 {"email": email("short"), "password": "short", "displayName": "X"})
        self.assertError(r, 400, "Bad Request", "password: size must be between 8 and 128")

    def test_register_blank_display_name_400(self):
        r = call("POST", "/api/v1/auth/register",
                 {"email": email("blank"), "password": "password123"})
        self.assertError(r, 400, "Bad Request", "displayName: must not be blank")

    def test_register_malformed_json_500(self):
        r = call("POST", "/api/v1/auth/register", raw_body="{bad")
        self.assertError(r, 500, "Internal Server Error", "Internal server error")

    def test_register_wrong_method_500(self):
        r = call("GET", "/api/v1/auth/register")
        self.assertError(r, 500, "Internal Server Error", "Internal server error")


class T04Login(CharacterizationBase):
    def test_login_ok_sets_last_login(self):
        reg = register("login")
        prof = call("GET", "/api/v1/auth/profile", token=reg["accessToken"]).json()
        self.assertIsNone(prof["lastLoginAt"])
        r = call("POST", "/api/v1/auth/login", {"email": email("login"), "password": "password123"})
        self.assertEqual(r.status, 200, r.text)
        b = r.json()
        self.assertEqual(list(b.keys()), ["accessToken", "refreshToken", "tokenType", "expiresIn", "user"])
        self.assertEqual(b["user"]["id"], reg["user"]["id"])
        prof = call("GET", "/api/v1/auth/profile", token=b["accessToken"]).json()
        self.assertRegex(prof["lastLoginAt"], ISO_RE)

    def test_login_wrong_password_400(self):
        register("badpw")
        r = call("POST", "/api/v1/auth/login", {"email": email("badpw"), "password": "wrongpass1"})
        self.assertError(r, 400, "Bad Request", "Invalid credentials")

    def test_login_unknown_user_400(self):
        r = call("POST", "/api/v1/auth/login", {"email": email("ghost"), "password": "password123"})
        self.assertError(r, 400, "Bad Request", "Invalid credentials")

    def test_login_blank_password_400(self):
        r = call("POST", "/api/v1/auth/login", {"email": email("x"), "password": ""})
        self.assertError(r, 400, "Bad Request", "password: must not be blank")

    def test_seeded_admin_documented_password_rejected(self):
        # V1 migration comment says Admin123!, but the seeded hash does not match it (pinned as-is)
        for pw in ["Admin123!", "password"]:
            r = call("POST", "/api/v1/auth/login", {"email": "admin@otterworks.dev", "password": pw})
            self.assertError(r, 400, "Bad Request", "Invalid credentials")


class T05Refresh(CharacterizationBase):
    def test_refresh_rotates_and_old_token_revoked(self):
        reg = register("refresh")
        time.sleep(1.1)
        r = call("POST", "/api/v1/auth/refresh", token=reg["refreshToken"])
        self.assertEqual(r.status, 200, r.text)
        b = r.json()
        self.assertEqual(list(b.keys()), ["accessToken", "refreshToken", "tokenType", "expiresIn", "user"])
        self.assertNotEqual(b["refreshToken"], reg["refreshToken"])
        self.assertEqual(b["user"]["id"], reg["user"]["id"])
        r2 = call("POST", "/api/v1/auth/refresh", token=reg["refreshToken"])
        self.assertError(r2, 400, "Bad Request", "Invalid or revoked refresh token")
        self.assertEqual(call("POST", "/api/v1/auth/refresh", token=b["refreshToken"]).status, 200)

    def test_refresh_with_access_token_400(self):
        reg = register("refacc")
        r = call("POST", "/api/v1/auth/refresh", token=reg["accessToken"])
        self.assertError(r, 400, "Bad Request", "Token is not a refresh token")

    def test_refresh_with_garbage_token_401(self):
        r = call("POST", "/api/v1/auth/refresh", token="garbage.token.value")
        self.assertError(r, 401, "Unauthorized", "Invalid or expired token")

    def test_refresh_with_bad_signature_401(self):
        reg = register("refsig")
        h, p, s = reg["refreshToken"].split(".")
        r = call("POST", "/api/v1/auth/refresh", token=h + "." + p + "." + s[:-4] + "AAAA")
        self.assertError(r, 401, "Unauthorized", "Invalid or expired token")

    def test_refresh_without_header_500(self):
        r = call("POST", "/api/v1/auth/refresh")
        self.assertError(r, 500, "Internal Server Error", "Internal server error")


class T06Profile(CharacterizationBase):
    def test_get_profile_shape(self):
        reg = register("prof", display="Prof User")
        r = call("GET", "/api/v1/auth/profile", token=reg["accessToken"])
        self.assertEqual(r.status, 200, r.text)
        self.assertEqual(r.header("Content-Type"), "application/json")
        b = r.json()
        self.assertEqual(list(b.keys()), ["id", "email", "displayName", "avatarUrl", "roles",
                                          "emailVerified", "createdAt", "updatedAt", "lastLoginAt"])
        self.assertEqual(b["id"], reg["user"]["id"])
        self.assertEqual(b["email"], email("prof"))
        self.assertEqual(b["displayName"], "Prof User")
        self.assertIsNone(b["avatarUrl"])
        self.assertEqual(b["roles"], ["USER"])
        self.assertIs(b["emailVerified"], False)
        self.assertRegex(b["createdAt"], ISO_RE)
        self.assertRegex(b["updatedAt"], ISO_RE)
        self.assertIsNone(b["lastLoginAt"])

    def test_profile_requires_auth_403(self):
        self.assertEmpty403(call("GET", "/api/v1/auth/profile"))

    def test_profile_with_invalid_token_403(self):
        self.assertEmpty403(call("GET", "/api/v1/auth/profile", token="garbage"))

    def test_profile_with_refresh_token_403(self):
        reg = register("profref")
        self.assertEmpty403(call("GET", "/api/v1/auth/profile", token=reg["refreshToken"]))

    def test_profile_of_deleted_or_unknown_subject_400(self):
        tok = mint_hs384({"sub": str(uuid.uuid4()), "roles": ["USER"], "type": "access",
                          "iat": int(time.time()), "exp": int(time.time()) + 600})
        self.assertError(call("GET", "/api/v1/auth/profile", token=tok), 400, "Bad Request", "User not found")

    def test_update_profile(self):
        reg = register("upd")
        r = call("PUT", "/api/v1/auth/profile",
                 {"displayName": "Updated Name", "avatarUrl": "https://cdn.example/a.png"},
                 token=reg["accessToken"])
        self.assertEqual(r.status, 200, r.text)
        b = r.json()
        self.assertEqual(b["displayName"], "Updated Name")
        self.assertEqual(b["avatarUrl"], "https://cdn.example/a.png")
        r = call("PUT", "/api/v1/auth/profile", {"avatarUrl": "https://cdn.example/b.png"},
                 token=reg["accessToken"])
        b = r.json()
        self.assertEqual(b["displayName"], "Updated Name")
        self.assertEqual(b["avatarUrl"], "https://cdn.example/b.png")
        again = call("GET", "/api/v1/auth/profile", token=reg["accessToken"]).json()
        self.assertEqual(again["displayName"], "Updated Name")

    def test_update_profile_empty_display_name_400(self):
        reg = register("updbad")
        r = call("PUT", "/api/v1/auth/profile", {"displayName": ""}, token=reg["accessToken"])
        self.assertError(r, 400, "Bad Request", "displayName: size must be between 1 and 100")

    def test_update_profile_requires_auth_403(self):
        self.assertEmpty403(call("PUT", "/api/v1/auth/profile", {"displayName": "x"}))


class T07ChangePassword(CharacterizationBase):
    def test_change_password_flow(self):
        reg = register("chpw")
        r = call("POST", "/api/v1/auth/change-password",
                 {"currentPassword": "password123", "newPassword": "newpassword456"},
                 token=reg["accessToken"])
        self.assertEqual(r.status, 204, r.text)
        self.assertEqual(r.raw, b"")
        self.assertError(call("POST", "/api/v1/auth/login",
                              {"email": email("chpw"), "password": "password123"}),
                         400, "Bad Request", "Invalid credentials")
        self.assertEqual(call("POST", "/api/v1/auth/login",
                              {"email": email("chpw"), "password": "newpassword456"}).status, 200)
        self.assertError(call("POST", "/api/v1/auth/refresh", token=reg["refreshToken"]),
                         400, "Bad Request", "Invalid or revoked refresh token")
        # the old access token keeps working (stateless JWT)
        self.assertEqual(call("GET", "/api/v1/auth/profile", token=reg["accessToken"]).status, 200)

    def test_change_password_wrong_current_400(self):
        reg = register("chpwbad")
        r = call("POST", "/api/v1/auth/change-password",
                 {"currentPassword": "nope-nope", "newPassword": "newpassword456"},
                 token=reg["accessToken"])
        self.assertError(r, 400, "Bad Request", "Current password is incorrect")

    def test_change_password_short_new_400(self):
        reg = register("chpwshort")
        r = call("POST", "/api/v1/auth/change-password",
                 {"currentPassword": "password123", "newPassword": "short"},
                 token=reg["accessToken"])
        self.assertError(r, 400, "Bad Request", "newPassword: size must be between 8 and 128")

    def test_change_password_requires_auth_403(self):
        self.assertEmpty403(call("POST", "/api/v1/auth/change-password",
                                 {"currentPassword": "a", "newPassword": "bbbbbbbb"}))


class T08Lookup(CharacterizationBase):
    def test_lookup_by_email(self):
        target = register("lookt", display="Look Target")
        caller = register("lookc")
        r = call("GET", "/api/v1/auth/users/lookup?email=" + email("lookt"), token=caller["accessToken"])
        self.assertEqual(r.status, 200, r.text)
        self.assertEqual(r.text, json.dumps({"id": target["user"]["id"], "email": email("lookt"),
                                             "displayName": "Look Target"}, separators=(",", ":")))

    def test_lookup_unknown_email_400(self):
        caller = register("lookunk")
        r = call("GET", "/api/v1/auth/users/lookup?email=nobody-" + RUN_ID + "@x.test",
                 token=caller["accessToken"])
        self.assertError(r, 400, "Bad Request", "User not found with email: nobody-" + RUN_ID + "@x.test")

    def test_lookup_missing_param_500(self):
        caller = register("lookmiss")
        r = call("GET", "/api/v1/auth/users/lookup", token=caller["accessToken"])
        self.assertError(r, 500, "Internal Server Error", "Internal server error")

    def test_lookup_requires_auth_403(self):
        self.assertEmpty403(call("GET", "/api/v1/auth/users/lookup?email=a@b.c"))

    def test_lookup_by_id(self):
        target = register("byid", display="By Id")
        caller = register("byidc")
        r = call("GET", "/api/v1/auth/users/by-id/" + target["user"]["id"], token=caller["accessToken"])
        self.assertEqual(r.status, 200, r.text)
        self.assertEqual(r.json(), {"id": target["user"]["id"], "email": email("byid"), "displayName": "By Id"})

    def test_lookup_seeded_admin_by_id(self):
        caller = register("byidadm")
        r = call("GET", "/api/v1/auth/users/by-id/" + SEED_ADMIN_ID, token=caller["accessToken"])
        self.assertEqual(r.status, 200, r.text)
        self.assertEqual(r.json(), {"id": SEED_ADMIN_ID, "email": "admin@otterworks.dev",
                                    "displayName": "Admin User"})

    def test_lookup_by_unknown_id_400(self):
        caller = register("byidunk")
        r = call("GET", "/api/v1/auth/users/by-id/" + str(uuid.uuid4()), token=caller["accessToken"])
        self.assertError(r, 400, "Bad Request", "User not found")

    def test_lookup_by_malformed_id_500(self):
        caller = register("byidbad")
        r = call("GET", "/api/v1/auth/users/by-id/not-a-uuid", token=caller["accessToken"])
        self.assertError(r, 500, "Internal Server Error", "Internal server error")

    def test_lookup_by_id_requires_auth_403(self):
        self.assertEmpty403(call("GET", "/api/v1/auth/users/by-id/" + SEED_ADMIN_ID))


class T09ListUsers(CharacterizationBase):
    def admin_token(self):
        now = int(time.time())
        return mint_hs384({"sub": SEED_ADMIN_ID, "roles": ["ADMIN", "USER"], "type": "access",
                           "iat": now, "exp": now + 600})

    def test_list_users_as_user_403(self):
        caller = register("listu")
        self.assertEmpty403(call("GET", "/api/v1/auth/users", token=caller["accessToken"]))

    def test_list_users_unauthenticated_403(self):
        self.assertEmpty403(call("GET", "/api/v1/auth/users"))

    def test_list_users_as_admin_page_shape(self):
        register("listadm")
        r = call("GET", "/api/v1/auth/users?size=2&page=0&sort=email,asc", token=self.admin_token())
        self.assertEqual(r.status, 200, r.text)
        self.assertEqual(r.header("Content-Type"), "application/json")
        b = r.json()
        self.assertEqual(list(b.keys()), ["content", "pageable", "last", "totalPages", "totalElements",
                                          "first", "size", "number", "sort", "numberOfElements", "empty"])
        self.assertEqual(list(b["pageable"].keys()),
                         ["pageNumber", "pageSize", "sort", "offset", "paged", "unpaged"])
        self.assertEqual(b["pageable"]["pageNumber"], 0)
        self.assertEqual(b["pageable"]["pageSize"], 2)
        self.assertEqual(b["pageable"]["sort"], {"empty": False, "sorted": True, "unsorted": False})
        self.assertEqual(b["sort"], {"empty": False, "sorted": True, "unsorted": False})
        self.assertEqual(b["pageable"]["offset"], 0)
        self.assertIs(b["pageable"]["paged"], True)
        self.assertIs(b["pageable"]["unpaged"], False)
        self.assertEqual(b["size"], 2)
        self.assertEqual(b["number"], 0)
        self.assertIs(b["first"], True)
        self.assertEqual(b["numberOfElements"], 2)
        self.assertGreaterEqual(b["totalElements"], 2)
        self.assertEqual(len(b["content"]), 2)
        self.assertEqual(list(b["content"][0].keys()),
                         ["id", "email", "displayName", "avatarUrl", "roles", "emailVerified",
                          "createdAt", "updatedAt", "lastLoginAt"])
        self.assertLessEqual(b["content"][0]["email"], b["content"][1]["email"])

    def test_list_users_admin_filter_by_url_rule_also_covers_subpaths(self):
        # /api/v1/auth/users/** is ADMIN-only at the URL layer; unmapped subpath as admin -> 500
        r = call("GET", "/api/v1/auth/users/anything", token=self.admin_token())
        self.assertError(r, 500, "Internal Server Error", "Internal server error")
        caller = register("listsub")
        self.assertEmpty403(call("GET", "/api/v1/auth/users/anything", token=caller["accessToken"]))


class T10Logout(CharacterizationBase):
    def test_logout_revokes_refresh_tokens(self):
        reg = register("logout")
        r = call("POST", "/api/v1/auth/logout", token=reg["accessToken"])
        self.assertEqual(r.status, 204, r.text)
        self.assertEqual(r.raw, b"")
        self.assertError(call("POST", "/api/v1/auth/refresh", token=reg["refreshToken"]),
                         400, "Bad Request", "Invalid or revoked refresh token")
        self.assertEqual(call("GET", "/api/v1/auth/profile", token=reg["accessToken"]).status, 200)

    def test_logout_requires_auth_403(self):
        self.assertEmpty403(call("POST", "/api/v1/auth/logout"))


class T11Settings(CharacterizationBase):
    def test_settings_defaults(self):
        reg = register("set")
        r = call("GET", "/api/v1/settings", token=reg["accessToken"])
        self.assertEqual(r.status, 200, r.text)
        self.assertEqual(r.header("Content-Type"), "application/json")
        self.assertEqual(r.text, '{"notificationEmail":true,"notificationInApp":true,'
                                 '"notificationDesktop":false,"theme":"system","language":"en"}')

    def test_settings_patch_partial_and_persisted(self):
        reg = register("setp")
        r = call("PATCH", "/api/v1/settings", {"theme": "dark", "notificationDesktop": True},
                 token=reg["accessToken"])
        self.assertEqual(r.status, 200, r.text)
        self.assertEqual(r.json(), {"notificationEmail": True, "notificationInApp": True,
                                    "notificationDesktop": True, "theme": "dark", "language": "en"})
        r = call("PATCH", "/api/v1/settings", {"language": "fr", "notificationEmail": False},
                 token=reg["accessToken"])
        self.assertEqual(r.json(), {"notificationEmail": False, "notificationInApp": True,
                                    "notificationDesktop": True, "theme": "dark", "language": "fr"})
        r = call("GET", "/api/v1/settings", token=reg["accessToken"])
        self.assertEqual(r.json()["language"], "fr")

    def test_settings_patch_without_existing_row_creates_it(self):
        reg = register("setnew")
        r = call("PATCH", "/api/v1/settings", {}, token=reg["accessToken"])
        self.assertEqual(r.status, 200, r.text)
        self.assertEqual(r.json()["theme"], "system")

    def test_settings_theme_too_long_500(self):
        reg = register("setlong")
        r = call("PATCH", "/api/v1/settings", {"theme": "x" * 11}, token=reg["accessToken"])
        self.assertError(r, 500, "Internal Server Error", "Internal server error")

    def test_settings_requires_auth_403(self):
        self.assertEmpty403(call("GET", "/api/v1/settings"))
        self.assertEmpty403(call("PATCH", "/api/v1/settings", {"theme": "dark"}))

    def test_settings_wrong_method_500(self):
        reg = register("setm")
        r = call("POST", "/api/v1/settings", {"theme": "dark"}, token=reg["accessToken"])
        self.assertError(r, 500, "Internal Server Error", "Internal server error")


class T12Misc(CharacterizationBase):
    def test_unknown_api_path_authenticated_500(self):
        reg = register("misc")
        r = call("GET", "/api/v1/nope", token=reg["accessToken"])
        self.assertError(r, 500, "Internal Server Error", "Internal server error")

    def test_cors_preflight_not_configured(self):
        r = call("OPTIONS", "/api/v1/auth/login",
                 headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
        self.assertEqual(r.status, 403, r.text)
        self.assertIsNone(r.header("Access-Control-Allow-Origin"))

    def test_expired_access_token_403(self):
        reg = register("exp")
        now = int(time.time())
        tok = mint_hs384({"sub": reg["user"]["id"], "roles": ["USER"], "type": "access",
                          "iat": now - 7200, "exp": now - 3600})
        self.assertEmpty403(call("GET", "/api/v1/auth/profile", token=tok))


if __name__ == "__main__":
    print("auth-service characterization against %s (run %s)" % (BASE, RUN_ID))
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2, stream=sys.stdout).run(suite)
    print("Tests run: %d, Failures: %d, Errors: %d, Skipped: %d"
          % (result.testsRun, len(result.failures), len(result.errors), len(result.skipped)))
    sys.exit(0 if result.wasSuccessful() else 1)
