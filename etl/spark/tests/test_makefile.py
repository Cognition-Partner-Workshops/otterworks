import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]


def dry_run(target, env, args=()):
    environment = {key: value for key, value in os.environ.items() if key not in ("SFX_SPARK_LANDING", "LANDING_DIR")}
    result = subprocess.run(
        ["make", "-n", "-C", str(REPO), target, "ROWS_PER_TABLE=20", *args],
        capture_output=True, text=True, check=True, env={**environment, **env},
    )
    return result.stdout.splitlines()


class MakefileLandingTest(unittest.TestCase):
    def test_override_drives_generation_mount_and_load(self):
        with tempfile.TemporaryDirectory() as landing:
            for env, args in (({"SFX_SPARK_LANDING": landing}, ()), ({}, (f"SFX_SPARK_LANDING={landing}",))):
                up = dry_run("sfx-spark-up", env, args)
                for line in up:
                    self.assertNotIn("LANDING_DIR=" + str(REPO), line)
                self.assertTrue(any(f"LANDING_DIR={landing} " in line and "load_tdemu.sh" in line for line in up))
                self.assertTrue(any(f"LANDING_DIR={landing} " in line for line in dry_run("sfx-spark-run", env, args)))
                generator = next(line for line in up if "--seed 1110" in line)
                self.assertIn(landing, generator)
                command = shlex.split(generator)
                command = command[command.index("python3"):]
                subprocess.run(command, cwd=REPO, check=True, capture_output=True, text=True)
                self.assertTrue(any(Path(landing).glob("*/*/*.psv")))


if __name__ == "__main__":
    unittest.main()
