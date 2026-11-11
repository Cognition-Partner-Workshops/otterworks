import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[3]


class RuntimeTest(unittest.TestCase):
    def test_landing_override(self):
        result = subprocess.run(
            ["make", "-n", "sfx-spark-up", "NS=sfx-d1110-check",
             "SFX_SPARK_LANDING=/tmp/sfx-landing-check", "ROWS_PER_TABLE=2000"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        commands = result.stdout
        self.assertRegex(commands, r'--rows 2000 --seed 1110 --(out|output) "/tmp/sfx-landing-check"')
        for command in commands.splitlines():
            if any(script in command for script in ("generate_fixture.py", "load_tdemu.sh", "docker compose")):
                self.assertIn("LANDING_DIR=/tmp/sfx-landing-check", command)
        self.assertIn("etl/spark/.data/sfx-d1110-check/eventlogs/", commands)
        self.assertIn("etl/spark/.cache/sfx-d1110-check", commands)

    @unittest.skipUnless(shutil.which("docker"), "Docker Compose CLI is not installed")
    def test_compose_namespaces(self):
        sources = []
        for namespace in ("sfx-d1110-before", "sfx-d1110-check"):
            environment = {key: value for key, value in os.environ.items() if key != "LANDING_DIR"}
            environment["NS"] = namespace
            result = subprocess.run(
                ["docker", "compose", "-f", "docker-compose.spark.yml", "config", "--format", "json"],
                cwd=ROOT, env=environment, capture_output=True, text=True, check=True,
            )
            services = json.loads(result.stdout)["services"]
            mounts = {mount["target"]: mount["source"] for mount in services["spark-master"]["volumes"]}
            for target in ("/opt/landing", "/opt/lake", "/opt/spark-events", "/opt/sfx/spark/.data"):
                self.assertIn(f"/.data/{namespace}", mounts[target])
            self.assertTrue(mounts["/opt/sfx/spark/.cache"].endswith(f"/.cache/{namespace}"))
            self.assertEqual(
                next(mount["source"] for mount in services["sfx-tdemu"]["volumes"] if mount["target"] == "/opt/landing"),
                mounts["/opt/landing"],
            )
            for service, port in (("spark-master", 7077), ("sfx-tdemu", 5432)):
                binding = next(item for item in services[service]["ports"] if item["target"] == port)
                self.assertEqual(binding["host_ip"], "127.0.0.1")
            sources.append({value for key, value in mounts.items() if key != "/opt/sfx/spark"})
        self.assertFalse(sources[0] & sources[1])
