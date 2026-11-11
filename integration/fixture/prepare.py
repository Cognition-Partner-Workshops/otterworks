import json
import os
import time
from pathlib import Path

import paramiko


def prepare():
    for attempt in range(40):
        try:
            transport = paramiko.Transport(("sftp", 22))
            transport.start_client(timeout=5)
            host_key = transport.get_remote_server_key()
            transport.auth_password(os.environ["REPLAY_SFTP_USER"], os.environ["REPLAY_SFTP_PASSWORD"])
            sftp = paramiko.SFTPClient.from_transport(transport)
            break
        except (OSError, paramiko.SSHException):
            if attempt == 39:
                raise
            time.sleep(0.25)
    try:
        keys = paramiko.HostKeys()
        keys.add("sftp", host_key.get_name(), host_key)
        keys.save("/state/known_hosts")
        for flow in Path("integration/corpus").glob("*/flow.json"):
            spec = json.loads(flow.read_text()).get("capture", {}).get("files")
            if spec:
                try:
                    sftp.mkdir(spec["root"])
                except OSError:
                    sftp.stat(spec["root"])
    finally:
        sftp.close()
        transport.close()
    print("Prepared isolated SFTP host key and per-flow output directories")


if __name__ == "__main__":
    prepare()
