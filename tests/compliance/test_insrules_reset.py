import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "failure", ["cobol.dat", "pharo.txt", "java.txt", "missing-output", ""]
)
def test_reset_batch_evidence(tmp_path, monkeypatch, failure):
    for name in ("Makefile", "legacy-rating/reset.sh", "legacy-rating/parity/driver.py"):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    for name in ("legacy-rating/fixtures", "legacy-rating/tables"):
        shutil.copytree(ROOT / name, tmp_path / name)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "add", "legacy-rating/fixtures", "legacy-rating/tables"],
        cwd=tmp_path,
        check=True,
    )

    docker = tmp_path / "docker"
    docker.write_text(f"#!{sys.executable}\n" + """\
import os
from pathlib import Path
import sys

name = Path(sys.argv[-1]).name
if name in {"cobol.dat", "pharo.txt", "java.txt"}:
    failure = os.environ["RESET_TEST_FAILURE"]
    if name == failure:
        print(f"batch failed: {name}", file=sys.stderr)
        sys.exit(12)
    if (name, failure) != ("cobol.dat", "missing-output"):
        row = "POL00001" + "0" * 72 if name == "cobol.dat" else "POL00001|OK||1|1|N|0||1|T"
        Path("legacy-rating/build", name).write_text(row + "\\n")
""")
    docker.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("RESET_TEST_FAILURE", failure)

    result = subprocess.run(
        ["make", "insrules-reset"], cwd=tmp_path, capture_output=True, text=True
    )
    report = tmp_path / "legacy-rating/build/parity.json"
    if failure:
        assert result.returncode != 0
        assert "INSRULES RESET" not in result.stdout
        assert not report.exists()
        if failure == "missing-output":
            assert "FileNotFoundError" in result.stderr
        else:
            assert f"batch failed: {failure}" in result.stderr
    else:
        assert result.returncode == 0, result.stderr
        assert "INSRULES RESET" in result.stdout
        assert any(pair["mismatched"] for pair in json.loads(report.read_text())["pairs"])
        strict = subprocess.run(
            ["make", "insrules-parity"], cwd=tmp_path, capture_output=True, text=True
        )
        assert strict.returncode != 0
        assert "mismatched=1" in strict.stdout
