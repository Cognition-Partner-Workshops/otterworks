from pathlib import Path

from harness import runner, settings


def test_runs_like_the_crontab_with_read_only_mounts():
    cmd = runner.docker_command(
        "img:tag", "analytics_daily", "2026-03-15T02:00:00Z", Path("/tmp/x/config.ini")
    )
    crontab = (settings.ETL_DIR / "crontab").read_text()
    assert "/opt/etl/run.sh analytics_daily.py" in crontab
    assert cmd[-3:] == ["img:tag", "/opt/etl/run.sh", "analytics_daily.py"]
    mounts = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == "--mount"]
    targets = {m.split("target=")[1].split(",")[0]: m for m in mounts}
    assert set(targets) == {
        "/opt/etl/run.sh",
        "/opt/etl/scripts",
        "/opt/etl/config.ini",
        "/opt/etl/sitecustomize.py",
    }
    assert all(m.endswith(",readonly") for m in mounts)
    assert "source=%s," % (settings.ETL_DIR / "config.ini") not in " ".join(mounts)
    assert "source=/tmp/x/config.ini," in targets["/opt/etl/config.ini"]
    assert "GOLDEN_FROZEN_TIME=2026-03-15T02:00:00Z" in cmd


def test_image_tag_tracks_legacy_pins():
    assert runner.image_tag().startswith(settings.LEGACY_IMAGE_REPO + ":")
    assert settings.ETL_DIR / "requirements.txt" in runner.IMAGE_INPUTS
