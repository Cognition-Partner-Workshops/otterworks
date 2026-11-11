"""Wait for selected Spring applications, not merely running containers."""
import argparse
import json
import re
import subprocess
import time

from .discover import MODULES


def wait_ready(namespace, modules, timeout=90, run=subprocess.run, clock=time.monotonic,
               sleep=time.sleep):
    pending = set(modules)
    deadline = clock() + timeout
    while pending:
        for module in sorted(pending):
            container = f"otterworks-tibco-{namespace}-{module}"
            state = json.loads(run(["docker", "inspect", "--format", "{{json .State}}", container],
                                   check=True, capture_output=True, text=True).stdout)
            if not state["Running"]:
                raise RuntimeError(f"{module}: container exited before readiness")
            logs = run(["docker", "logs", "--since", state["StartedAt"], container],
                       check=True, capture_output=True, text=True)
            if re.search(r"Started \w+Application in", logs.stdout + logs.stderr):
                print(f"{module}: application ready", flush=True)
                pending.remove(module)
        if not pending:
            return
        if clock() >= deadline:
            raise TimeoutError(f"Applications not ready: {sorted(pending)}")
        sleep(0.5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("namespace")
    parser.add_argument("modules", nargs="+", choices=sorted(MODULES))
    args = parser.parse_args()
    wait_ready(args.namespace, args.modules)


if __name__ == "__main__":
    main()
