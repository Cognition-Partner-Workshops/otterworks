"""Tests for the export archive reader."""

import pytest

from app.services import export_archive
from app.services.export_archive import ExportArchive


@pytest.fixture
def archive(tmp_path):
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


@pytest.mark.asyncio
async def test_export_endpoint_serves_archived_file(client, monkeypatch, tmp_path):
    (tmp_path / "report.md").write_text("# Report\n", encoding="utf-8")
    monkeypatch.setenv("EXPORT_ARCHIVE_DIR", str(tmp_path))

    resp = await client.get("/api/v1/documents/exports", params={"name": "report.md"})

    assert resp.status_code == 200
    assert resp.text == "# Report\n"


@pytest.mark.asyncio
async def test_export_endpoint_404s_for_unknown_name(client, monkeypatch, tmp_path):
    monkeypatch.setenv("EXPORT_ARCHIVE_DIR", str(tmp_path))

    resp = await client.get("/api/v1/documents/exports", params={"name": "absent.md"})

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_export_endpoint_404s_for_undecodable_file(client, monkeypatch, tmp_path):
    (tmp_path / "report.bin").write_bytes(b"\xff\xfe\x00binary")
    monkeypatch.setenv("EXPORT_ARCHIVE_DIR", str(tmp_path))

    resp = await client.get("/api/v1/documents/exports", params={"name": "report.bin"})

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_export_endpoint_404s_for_unreadable_file(client, monkeypatch, tmp_path):
    (tmp_path / "locked.md").write_text("# Locked\n", encoding="utf-8")
    monkeypatch.setenv("EXPORT_ARCHIVE_DIR", str(tmp_path))

    def refuse(*args, **kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(export_archive, "open", refuse, raising=False)

    resp = await client.get("/api/v1/documents/exports", params={"name": "locked.md"})

    assert resp.status_code == 404


@pytest.fixture
def outside_file(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    secret = outside / "tenant-secrets.env"
    secret.write_text("SUPPLIER_API_KEY=leaked\n", encoding="utf-8")
    return secret


@pytest.mark.parametrize(
    "name",
    [
        "../../etc/passwd",
        "/etc/passwd",
        "reports/../../etc/passwd",
        "report.md\x00.txt",
    ],
)
def test_rejects_names_that_escape_the_archive(archive, name):
    with pytest.raises(FileNotFoundError):
        archive.read_export(name)


def test_rejects_traversal_to_sibling_directory(archive, outside_file):
    with pytest.raises(FileNotFoundError):
        archive.read_export(f"../{outside_file.parent.name}/{outside_file.name}")


def test_rejects_symlink_pointing_outside_the_archive(archive, tmp_path, outside_file):
    (tmp_path / "escape.md").symlink_to(outside_file)
    with pytest.raises(FileNotFoundError):
        archive.read_export("escape.md")


def test_rejects_symlinked_directory_outside_the_archive(archive, tmp_path, outside_file):
    (tmp_path / "linked").symlink_to(outside_file.parent, target_is_directory=True)
    with pytest.raises(FileNotFoundError):
        archive.read_export(f"linked/{outside_file.name}")


def test_resolves_export_path_inside_archive(archive, tmp_path):
    resolved = archive.resolve_export_path("reports/q3.md")
    assert resolved == str((tmp_path / "reports" / "q3.md").resolve())


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["../../etc/passwd", "/etc/passwd"])
async def test_export_endpoint_404s_for_traversal(client, monkeypatch, tmp_path, name):
    (tmp_path / "report.md").write_text("# Report\n", encoding="utf-8")
    monkeypatch.setenv("EXPORT_ARCHIVE_DIR", str(tmp_path))

    resp = await client.get("/api/v1/documents/exports", params={"name": name})

    assert resp.status_code == 404
    assert "root:" not in resp.text


@pytest.mark.asyncio
async def test_export_endpoint_404s_for_symlink_outside_archive(
    client, monkeypatch, tmp_path, outside_file
):
    (tmp_path / "escape.md").symlink_to(outside_file)
    monkeypatch.setenv("EXPORT_ARCHIVE_DIR", str(tmp_path))

    resp = await client.get("/api/v1/documents/exports", params={"name": "escape.md"})

    assert resp.status_code == 404
    assert "SUPPLIER_API_KEY" not in resp.text


@pytest.mark.asyncio
async def test_export_endpoint_still_serves_subdirectory_export(client, monkeypatch, tmp_path):
    nested = tmp_path / "reports"
    nested.mkdir()
    (nested / "q3.md").write_text("# Q3\n", encoding="utf-8")
    monkeypatch.setenv("EXPORT_ARCHIVE_DIR", str(tmp_path))

    resp = await client.get("/api/v1/documents/exports", params={"name": "reports/q3.md"})

    assert resp.status_code == 200
    assert resp.text == "# Q3\n"
