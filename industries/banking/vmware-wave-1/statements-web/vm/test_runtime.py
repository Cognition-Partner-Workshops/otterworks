#!/usr/bin/env python3
"""Exercise a locally built image with an isolated synthetic database (no cloud)."""

import argparse
import hashlib
import http.cookiejar
import json
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.request


def docker(*args, input=None):
    return subprocess.run(
        ["docker", *args], input=input, text=True, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120,
    ).stdout.strip()


def exercise(image, run_token, out, hardened):
    docker("image", "inspect", image)
    network = run_token + "-net"
    db = run_token + "-db"
    web = run_token + "-web"
    created = []
    try:
        docker("network", "create", network)
        created.append(("network", network))
        docker("run", "-d", "--name", db, "--network", network,
               "--network-alias", "fixture-db", "-e", "POSTGRES_DB=fixture",
               "-e", "POSTGRES_USER=fixture", "-e", "POSTGRES_PASSWORD=synthetic-only",
               "postgres:16")
        created.append(("container", db))
        for attempt in range(60):
            try:
                docker("exec", db, "pg_isready", "-h", "127.0.0.1", "-U", "fixture", "-d", "fixture")
                break
            except subprocess.CalledProcessError:
                time.sleep(1)
        else:
            raise AssertionError("synthetic database did not become ready")
        docker("exec", "-i", db, "psql", "-v", "ON_ERROR_STOP=1", "-U", "fixture",
               "-d", "fixture", input="""
CREATE TABLE accounts (account_id text PRIMARY KEY, holder text);
CREATE TABLE statement_lines (id serial PRIMARY KEY, account_id text,
    booked date, description text, amount numeric(12,2), balance numeric(12,2));
INSERT INTO accounts VALUES ('TEST000001', 'Synthetic A'), ('TEST000002', 'Synthetic B');
INSERT INTO statement_lines (account_id, booked, description, amount, balance) VALUES
    ('TEST000001', '2026-10-14', 'Fixture credit', 100.00, 100.00),
    ('TEST000001', '2026-10-15', 'Fixture debit', -30.50, 69.50),
    ('TEST000002', '2026-10-16', 'Fixture second account', 25.00, 25.00);
""")
        context = out / "context.xml"
        context.write_text('''<Context><Resource name="jdbc/StatementsDB" auth="Container"
type="javax.sql.DataSource" driverClassName="org.postgresql.Driver"
url="jdbc:postgresql://fixture-db:5432/fixture" username="fixture"
password="synthetic-only" maxTotal="4"/></Context>''')
        settings = out / "statements.properties"
        settings.write_text("bank.name=Synthetic statements\nstatement.page.size=50\n")
        context.chmod(0o644)
        settings.chmod(0o644)
        args = ["run", "-d", "--name", web, "--network", network,
                "-p", "127.0.0.1::8080", "--memory", "256m", "--cpus", "0.5",
                "--mount", f"type=bind,src={context},dst=/usr/local/tomcat/conf/context.xml,readonly",
                "--mount", f"type=bind,src={settings},dst=/opt/app/conf/statements.properties,readonly"]
        if hardened:
            args += ["--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                     "--tmpfs", "/tmp:uid=10001,gid=10001,mode=1777",
                     "--tmpfs", "/usr/local/tomcat/temp:uid=10001,gid=10001,mode=700",
                     "--tmpfs", "/usr/local/tomcat/work:uid=10001,gid=10001,mode=700"]
        docker(*args, image)
        created.append(("container", web))
        port = docker("port", web, "8080/tcp").split(":")[-1]
        base = f"http://127.0.0.1:{port}/statements/"
        client = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        for attempt in range(90):
            try:
                with client.open(base + "accounts", timeout=2) as response:
                    assert response.status == 200
                break
            except (urllib.error.URLError, TimeoutError, ConnectionResetError):
                time.sleep(1)
        else:
            raise AssertionError("statements servlet did not become ready")
        cases = [
            ("accounts", "accounts", 200, b"Synthetic A"),
            ("statement-a", "statement?account=TEST000001", 200, b"2 lines, net movement 69.50"),
            ("last-account", "accounts", 200, b"Last viewed:"),
            ("statement-b", "statement?account=TEST000002", 200, b"1 lines, net movement 25.00"),
            ("empty-statement", "statement?account=TEST999999", 200, b"0 lines, net movement 0"),
            ("missing-account", "statement", 400, None),
            ("malformed-account", "statement?account=bad!", 400, None),
        ]
        responses = {}
        for name, path, expected_status, expected_body in cases:
            try:
                response = client.open(base + path, timeout=5)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                body = response.read()
                assert response.status == expected_status, (name, response.status)
                if expected_body:
                    assert expected_body in body, name
                responses[name] = {"status": response.status}
                if expected_status == 200:
                    responses[name]["sha256"] = hashlib.sha256(body).hexdigest()
        uid = docker("exec", web, "id", "-u")
        # java -version uses stderr.
        java = subprocess.run(["docker", "exec", web, "java", "-version"],
                              capture_output=True, text=True, check=True, timeout=30).stderr
        tomcat = docker("exec", web, "/usr/local/tomcat/bin/version.sh")
        if hardened:
            assert uid == "10001", uid
            assert 'version "17.' in java, java
            assert "Apache Tomcat/9.0." in tomcat, tomcat
            denied = subprocess.run(["docker", "exec", web, "touch", "/root/runtime-write"],
                                    capture_output=True, timeout=10)
            assert denied.returncode != 0, "non-root process must not write into /root"
        logs = docker("logs", web)
        if hardened:
            assert "statement viewed account=TEST000001" in logs, "application log missing from stdout"
        report = {"image": image, "uid": uid, "java": java, "tomcat": tomcat,
                  "read_only": hardened, "responses": responses}
        (out / "runtime.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
    finally:
        for kind, name in reversed(created):
            if kind == "container":
                if name == web:
                    logs = subprocess.run(["docker", "logs", web], capture_output=True,
                                          text=True, timeout=30)
                    (out / "web.log").write_text(logs.stdout + logs.stderr)
                docker("rm", "-fv", name)
            else:
                docker("network", "rm", name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="pre-built local image; never published")
    parser.add_argument("--run-token", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--hardened", action="store_true")
    options = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,60}", options.run_token):
        parser.error("run-token must be a unique lowercase Docker resource prefix")
    options.out = options.out.resolve()
    options.out.mkdir(parents=True, exist_ok=True)
    exercise(options.image, options.run_token, options.out, options.hardened)
