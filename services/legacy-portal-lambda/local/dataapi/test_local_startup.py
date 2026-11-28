import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[4] / "scripts/lp-local.sh"


class StartupTest(unittest.TestCase):
    def test_up_reloads_data_api_even_when_shared_material_is_already_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            mock_env = Path(tmp) / "bash-env"
            calls = Path(tmp) / "docker-calls"
            mock_env.write_text(
                'docker() {\n'
                '  printf "%s\\n" "$*" >> "$DOCKER_CALLS"\n'
                '  if [[ "$*" == *"exec -T dataapi python3"* ]] && [ ! -e "$DOCKER_CALLS.probed" ]; then\n'
                '    touch "$DOCKER_CALLS.probed"\n'
                '    return 1\n'
                '  fi\n'
                '}\n'
                'curl() { return 0; }\n'
                'sleep() { return 0; }\n'
            )
            subprocess.run(
                ["bash", SCRIPT, "up"],
                env={**os.environ, "BASH_ENV": str(mock_env), "DOCKER_CALLS": str(calls),
                     "RUN_TOKEN": "STARTUP_TEST"},
                check=True, capture_output=True, text=True,
            )
            commands = calls.read_text().splitlines()

        def command_index(suffix):
            return next(i for i, command in enumerate(commands) if command.endswith(suffix))

        self.assertLess(command_index("run --rm --no-deps -T certs"), command_index("up -d --build"))
        self.assertLess(command_index("up -d --build"), command_index("restart dataapi"))
        self.assertLess(command_index("restart dataapi"),
                        command_index("restart fn-announcements fn-preferences fn-feedback"))
        first, retry = (i for i, command in enumerate(commands) if "exec -T dataapi python3" in command)
        self.assertLess(command_index("restart dataapi"), first)
        self.assertLess(first, retry)
        self.assertLess(retry, command_index("restart fn-announcements fn-preferences fn-feedback"))
