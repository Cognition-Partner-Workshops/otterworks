"""Tests for the export archive reader."""

import pytest

from app.services import export_archive
from app.services.export_archive import ExportArchive
from tests.conftest import auth_headers

CALLER = "aaaaaaaa-0000-4000-8000-00000000000a"


@pytest.fixture
def archive(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (outside / "secret.env").write_text("SECRET=1\n", encoding="utf-8")
    (tmp_path / "report.md").write_text("# Report\n", encoding="utf-8")
    nested = tmp_path / "reports"
    nested.mkdir()
    (nested / "q3.md").write_text("# Q3\n", encoding="utf-8")
    return ExportArchive(base_dir=str(tmp_path))


def test_reads_export(archive):
    assert archive.read_export("report.md") == "# Report\n"


def test_reads_export_in_subdirectory(archive):
    assert archive.read_export("reports/q3.md") == "# Q3\n"


def test_missing_export_raises(archive):
    with pytest.raises(FileNotFoundError):
        archive.read_export("absent.md")


@pytest.mark.parametrize(
    "name",
    [
        "../{outside}/secret.env",
        "reports/../../{outside}/secret.env",
        "{root}/../{outside}/secret.env",
        "/etc/passwd",
        "/proc/self/environ",
        ".",
        "reports/..",
    ],
)
def test_names_outside_the_archive_are_refused(archive, tmp_path, name):
    name = name.format(outside=f"{tmp_path.name}-outside", root=tmp_path)
    with pytest.raises(FileNotFoundError):
        archive.read_export(name)


def test_symlink_out_of_the_archive_is_refused(archive, tmp_path):
    (tmp_path / "link.env").symlink_to(tmp_path.parent / f"{tmp_path.name}-outside" / "secret.env")
    with pytest.raises(FileNotFoundError):
        archive.read_export("link.env")


@pytest.mark.asyncio
async def test_export_endpoint_requires_authentication(client, monkeypatch, tmp_path):
    (tmp_path / "report.md").write_text("# Report\n", encoding="utf-8")
    monkeypatch.setenv("EXPORT_ARCHIVE_DIR", str(tmp_path))

    resp = await client.get(
        "/api/v1/documents/exports",
        params={"name": "report.md"},
        headers={"X-User-ID": CALLER},
    )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_export_endpoint_404s_for_traversal(client, monkeypatch, tmp_path):
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    (tmp_path / "secret.env").write_text("SECRET=1\n", encoding="utf-8")
    monkeypatch.setenv("EXPORT_ARCHIVE_DIR", str(archive_dir))

    for name in ("../secret.env", str(tmp_path / "secret.env"), "/proc/self/environ"):
        resp = await client.get(
            "/api/v1/documents/exports", params={"name": name}, headers=auth_headers(CALLER)
        )
        assert resp.status_code == 404
        assert "SECRET" not in resp.text


@pytest.mark.asyncio
async def test_export_endpoint_serves_archived_file(client, monkeypatch, tmp_path):
    (tmp_path / "report.md").write_text("# Report\n", encoding="utf-8")
    monkeypatch.setenv("EXPORT_ARCHIVE_DIR", str(tmp_path))

    resp = await client.get(
        "/api/v1/documents/exports", params={"name": "report.md"}, headers=auth_headers(CALLER)
    )

    assert resp.status_code == 200
    assert resp.text == "# Report\n"


@pytest.mark.asyncio
async def test_export_endpoint_404s_for_unknown_name(client, monkeypatch, tmp_path):
    monkeypatch.setenv("EXPORT_ARCHIVE_DIR", str(tmp_path))

    resp = await client.get(
        "/api/v1/documents/exports", params={"name": "absent.md"}, headers=auth_headers(CALLER)
    )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_export_endpoint_404s_for_undecodable_file(client, monkeypatch, tmp_path):
    (tmp_path / "report.bin").write_bytes(b"\xff\xfe\x00binary")
    monkeypatch.setenv("EXPORT_ARCHIVE_DIR", str(tmp_path))

    resp = await client.get(
        "/api/v1/documents/exports", params={"name": "report.bin"}, headers=auth_headers(CALLER)
    )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_export_endpoint_404s_for_unreadable_file(client, monkeypatch, tmp_path):
    (tmp_path / "locked.md").write_text("# Locked\n", encoding="utf-8")
    monkeypatch.setenv("EXPORT_ARCHIVE_DIR", str(tmp_path))

    def refuse(*args, **kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(export_archive, "open", refuse, raising=False)

    resp = await client.get(
        "/api/v1/documents/exports", params={"name": "locked.md"}, headers=auth_headers(CALLER)
    )

    assert resp.status_code == 404
