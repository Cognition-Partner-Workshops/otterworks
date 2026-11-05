"""Exercise the real Makefile with local, stateful command mocks only."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


MOCK = r"""#!/usr/bin/python3
import json
import os
from pathlib import Path
import sys

state_file = Path(os.environ["MOCK_STATE"])
state = json.loads(state_file.read_text())
tool, args = Path(sys.argv[0]).name, sys.argv[1:]
state["calls"].append([tool, *args])
output = ""
code = 0
if tool == "kubectl":
    if args[:2] == ["get", "ns"]:
        run = args[args.index("-l") + 1].split("=", 1)[1]
        output = "\n".join(ns for ns in state["namespaces"]
                           if ns.startswith("namespace/bank-w1-" + run + "-pr"))
    elif args[0] == "delete":
        if not state.get("stuck_namespace"):
            state["namespaces"].remove(args[1])
    else:
        code = 97
elif tool == "helm":
    if args[0] == "list":
        output = "fixture-app"
    elif args[0] != "uninstall":
        code = 97
elif tool == "aws":
    if args[0] == "resourcegroupstaggingapi":
        arns = state["tagged"]
        query = args[args.index("--query") + 1]
        if "!contains(ResourceARN, ':ecr:')" in query:
            arns = [arn for arn in arns if ":ecr:" not in arn]
        output = "\t".join(arns)
    elif args[:2] == ["ecr", "delete-repository"]:
        repository = args[args.index("--repository-name") + 1]
        state["repositories"].remove(repository)
        state["tagged"] = [arn for arn in state["tagged"]
                           if not arn.endswith("repository/" + repository)]
    elif args[:2] == ["ecr", "describe-repositories"]:
        repository = args[args.index("--repository-names") + 1]
        if repository in state["repositories"]:
            output = repository
        else:
            code = 1
    elif args[:2] == ["ecr", "create-repository"]:
        state["repositories"].append(args[args.index("--repository-name") + 1])
    elif args[:2] != ["ecr", "put-lifecycle-policy"]:
        code = 97
else:
    code = 97
state_file.write_text(json.dumps(state))
if output:
    print(output)
sys.exit(code)
"""


class ResourceOwnershipTest(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(
            prefix="mod05-f875-shared-resource-ownership-"
        )
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for command in ("aws", "kubectl", "helm"):
            script = self.bin / command
            script.write_text(MOCK)
            script.chmod(0o755)
        date = shutil.which("date")
        make = shutil.which("make")
        assert date is not None and make is not None
        (self.bin / "date").symlink_to(date)
        self.make = make
        self.state_file = self.root / "state.json"
        self.makefile = Path(
            os.environ.get("WAVE1_MAKEFILE", str(Path(__file__).with_name("Makefile")))
        )

    def run_make(self, target="destroy", run="runone", **overrides):
        state = {
            "calls": [],
            "namespaces": ["namespace/bank-w1-runone-pr7"],
            "repositories": ["otterworks/bank-statements-web"],
            "tagged": [
                "arn:aws:ecr:us-east-1:000000000000:repository/otterworks/bank-statements-web"
            ],
            **overrides,
        }
        self.state_file.write_text(json.dumps(state))
        result = subprocess.run(
            [
                self.make,
                "--no-print-directory",
                "-rR",
                "-f",
                str(self.makefile),
                target,
                f"RUN={run}",
            ],
            cwd=self.root,
            env={
                "PATH": str(self.bin),
                "MOCK_STATE": str(self.state_file),
                "LC_ALL": "C",
            },
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result, json.loads(self.state_file.read_text())

    def test_destroy_retains_shared_repository_even_with_stale_run_tag(self):
        result, state = self.run_make()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(state["repositories"], ["otterworks/bank-statements-web"])
        self.assertFalse(any(call[:2] == ["aws", "ecr"] for call in state["calls"]))

    def test_destroy_still_uninstalls_releases_and_removes_run_namespace(self):
        result, state = self.run_make()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(state["namespaces"], [])
        self.assertIn(
            ["helm", "uninstall", "fixture-app", "-n", "bank-w1-runone-pr7", "--wait"],
            state["calls"],
        )
        for call in state["calls"]:
            if call[:3] == ["kubectl", "get", "ns"]:
                self.assertIn("demo/run-token=runone", call)

    def test_destroy_is_idempotent_without_owned_resources(self):
        result, state = self.run_make(namespaces=[])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(state["repositories"], ["otterworks/bank-statements-web"])

    def test_destroy_fails_when_owned_namespace_remains(self):
        result, _ = self.run_make(stuck_namespace=True)
        self.assertNotEqual(result.returncode, 0)

    def test_destroy_leaves_other_runs_namespaces_and_untagged_shared_repositories(
        self,
    ):
        result, state = self.run_make(
            namespaces=["namespace/bank-w1-runone-pr7", "namespace/bank-w1-runtwo-pr8"],
            tagged=[],
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(state["namespaces"], ["namespace/bank-w1-runtwo-pr8"])
        self.assertEqual(state["repositories"], ["otterworks/bank-statements-web"])
        self.assertFalse(any(call[:2] == ["aws", "ecr"] for call in state["calls"]))

    def test_destroy_fails_when_other_run_tagged_resource_remains(self):
        result, _ = self.run_make(tagged=["arn:aws:s3:::synthetic-run-fixture"])
        self.assertNotEqual(result.returncode, 0)

    def test_invalid_run_cannot_invoke_any_external_command(self):
        for run in ("", "bad-token", "UPPER", "run;exit"):
            with self.subTest(run=run):
                result, state = self.run_make(run=run)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(state["calls"], [])

    def test_ecr_creation_does_not_claim_shared_repositories_for_a_run(self):
        result, state = self.run_make(target="ecr", repositories=[], tagged=[])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        creates = [
            call
            for call in state["calls"]
            if call[:3] == ["aws", "ecr", "create-repository"]
        ]
        self.assertEqual(len(creates), 6)
        for call in creates:
            self.assertIn("Key=Project,Value=otterworks-bank-wave1", call)
            self.assertFalse(
                any("run_token" in arg or "Expires" in arg for arg in call)
            )

    def test_ecr_existing_repositories_keep_shared_names_and_lifecycle_policy(self):
        result, state = self.run_make(target="ecr")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        policies = [
            call
            for call in state["calls"]
            if call[:3] == ["aws", "ecr", "put-lifecycle-policy"]
        ]
        self.assertEqual(len(policies), 6)
        self.assertIn("otterworks/bank-statements-web", state["repositories"])
        self.assertFalse(
            any(
                call[:3] == ["aws", "ecr", "delete-repository"]
                for call in state["calls"]
            )
        )


if __name__ == "__main__":
    unittest.main()
