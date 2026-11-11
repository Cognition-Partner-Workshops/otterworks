from __future__ import annotations

import base64
import io
import os
import stat
import threading
import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse


def env_value(spec: dict, key: str, default=None):
    return os.environ[spec[f"{key}_env"]] if f"{key}_env" in spec else spec.get(key, default)


def safe_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError(f"Path escapes root: {relative}")
    return path


def remote_path(root: str, relative: str) -> str:
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"Invalid relative SFTP path: {relative}")
    return str(PurePosixPath(root) / path)


def normalized(value):
    if isinstance(value, (Decimal, date, datetime, uuid.UUID)):
        return str(value)
    if isinstance(value, bytes):
        return {"base64": base64.b64encode(value).decode()}
    if isinstance(value, dict):
        return {key: normalized(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalized(item) for item in value]
    return value


class Broker:
    """STOMP 1.2 with receipts and explicit Artemis subscription headers."""

    def __init__(self, config: dict, captures: list[dict]):
        self.config = config
        self.captures = captures
        self.messages = []
        self.errors = []
        self.receipts = {}
        self.mutex = threading.Lock()
        self.connections = []

    def open(self):
        import stomp

        owner = self

        class Listener(stomp.ConnectionListener):
            def on_message(self, frame):
                headers = dict(frame.headers)
                subscription = headers.get("subscription")
                destination = next((c["destination"] for c in owner.captures
                                    if c["id"] == subscription), headers.get("destination"))
                with owner.mutex:
                    owner.messages.append({"destination": destination, "body": frame.body,
                                           "headers": headers})

            def on_receipt(self, frame):
                with owner.mutex:
                    event = owner.receipts.get(frame.headers.get("receipt-id"))
                if event:
                    event.set()

            def on_error(self, frame):
                with owner.mutex:
                    owner.errors.append("STOMP broker returned ERROR")

        url = urlparse(env_value(self.config, "url"))
        if url.scheme not in ("stomp", "stomps") or not url.hostname:
            raise ValueError("Broker URL must use stomp:// or stomps://")
        for role in ("observer", "publisher"):
            conn = stomp.Connection12([(url.hostname, url.port or 61613)], heartbeats=(10000, 10000))
            if url.scheme == "stomps":
                conn.set_ssl(for_hosts=[(url.hostname, url.port or 61613)])
            conn.set_listener("capture", Listener())
            headers = {}
            if role == "observer" and self.config.get("client_id"):
                headers["client-id"] = self.config["client_id"]
            self.connections.append(conn)
            conn.connect(env_value(self.config, "username", ""),
                         env_value(self.config, "password", ""), wait=True, headers=headers)
            if role == "observer":
                for capture in self.captures:
                    self._receipt(conn.subscribe, destination=capture["destination"],
                                  id=capture["id"], ack="auto", headers=capture.get("headers", {}))

    def _receipt(self, operation, **kwargs):
        receipt = str(uuid.uuid4())
        event = threading.Event()
        with self.mutex:
            self.receipts[receipt] = event
        headers = dict(kwargs.pop("headers", {}), receipt=receipt)
        try:
            operation(headers=headers, **kwargs)
            if not event.wait(float(self.config.get("receipt_timeout", 10))):
                raise TimeoutError("STOMP receipt timeout; delivery outcome is unknown, not retried")
            self.check()
        finally:
            with self.mutex:
                self.receipts.pop(receipt, None)

    def send(self, message: dict):
        headers = {**message.get("properties", {}), **message.get("headers", {})}
        headers.setdefault("persistent", "true")
        headers["content-length"] = len(message["body"].encode("utf-8"))
        self._receipt(self.connections[1].send, destination=message["destination"],
                      body=message["body"], headers=headers)

    def check(self):
        if self.errors:
            raise RuntimeError(self.errors[0])
        if any(not conn.is_connected() for conn in self.connections):
            raise ConnectionError("STOMP disconnected during capture")

    def snapshot(self):
        self.check()
        with self.mutex:
            return list(self.messages)

    def close(self):
        for conn in self.connections:
            if conn.is_connected():
                conn.disconnect()
        self.connections = []

    def reconnect(self):
        self.close()
        self.open()


class Resources:
    def __init__(self, config: dict):
        self.config = config

    def _sftp(self):
        import paramiko

        spec = self.config["sftp"]
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        if spec.get("known_hosts"):
            client.load_host_keys(spec["known_hosts"])
        client.connect(spec["host"], port=spec.get("port", 22),
                       username=env_value(spec, "username"), password=env_value(spec, "password"),
                       key_filename=spec.get("key_filename"), timeout=10)
        return client, client.open_sftp()

    def drop(self, item: dict):
        client, sftp = self._sftp()
        try:
            path = remote_path(self.config["sftp"]["input_root"], item["path"])
            data = base64.b64decode(item["base64"], validate=True)
            sftp.putfo(io.BytesIO(data), path + ".replay-part")
            sftp.rename(path + ".replay-part", path)
        finally:
            sftp.close()
            client.close()

    def database(self, tables: dict) -> dict:
        if not tables:
            return {}
        import psycopg
        from psycopg.rows import dict_row

        result = {}
        with psycopg.connect(env_value(self.config["db"], "dsn"), row_factory=dict_row,
                             connect_timeout=10) as conn:
            conn.read_only = True
            for name, spec in tables.items():
                result[name] = normalized(conn.execute(spec["query"], spec.get("params", [])).fetchall())
        return result

    def files(self, spec: dict | None) -> dict:
        if not spec:
            return {}
        if spec["transport"] == "directory":
            root = Path(spec["root"]).resolve()
            if not root.is_dir():
                raise ValueError("Output directory does not exist")
            result = {}
            for path in sorted(root.rglob("*")):
                if path.is_symlink():
                    raise ValueError("Output symlink refused")
                if path.is_file():
                    result[path.relative_to(root).as_posix()] = base64.b64encode(path.read_bytes()).decode()
            return result
        if spec["transport"] != "sftp":
            raise ValueError("Unknown file capture transport")
        client, sftp = self._sftp()
        result = {}

        def walk(relative=""):
            directory = spec["root"] if not relative else remote_path(spec["root"], relative)
            for entry in sftp.listdir_attr(directory):
                name = str(PurePosixPath(relative) / entry.filename)
                if stat.S_ISDIR(entry.st_mode):
                    walk(name)
                elif stat.S_ISREG(entry.st_mode):
                    with sftp.open(remote_path(spec["root"], name), "rb") as handle:
                        result[name] = base64.b64encode(handle.read()).decode()
                else:
                    raise ValueError("Non-regular SFTP output refused")
        try:
            walk()
            return result
        finally:
            sftp.close()
            client.close()
