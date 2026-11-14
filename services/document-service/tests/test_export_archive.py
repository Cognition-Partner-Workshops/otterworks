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
def archive_with_neighbour(tmp_path):
    root = tmp_path / "archive"
    root.mkdir()
    (root / "report.md").write_text("# Report\n", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secrets.env").write_text("SUPPLIER_API_KEY=leak\n", encoding="utf-8")
    return root, outside


@pytest.mark.parametrize(
    "name",
    [
        "../outside/secrets.env",
        "reports/../../outside/secrets.env",
        "/etc/passwd",
        "/proc/self/environ",
        "report.md\x00.txt",
    ],
)
def test_rejects_names_that_escape_the_archive(archive_with_neighbour, name):
    root, _ = archive_with_neighbour
    archive = ExportArchive(base_dir=str(root))

    with pytest.raises(PermissionError):
        archive.read_export(name)


def test_rejects_symlink_pointing_outside_the_archive(archive_with_neighbour):
    root, outside = archive_with_neighbour
    (root / "link.env").symlink_to(outside / "secrets.env")
    archive = ExportArchive(base_dir=str(root))

    with pytest.raises(PermissionError):
        archive.read_export("link.env")


def test_allows_dot_segments_that_stay_inside(archive_with_neighbour):
    root, _ = archive_with_neighbour
    (root / "reports").mkdir()
    archive = ExportArchive(base_dir=str(root))

    assert archive.read_export("reports/../report.md") == "# Report\n"


def test_rejects_sibling_with_shared_prefix(tmp_path):
    root = tmp_path / "exports"
    root.mkdir()
    sibling = tmp_path / "exports-private"
    sibling.mkdir()
    (sibling / "secret.md").write_text("secret\n", encoding="utf-8")
    archive = ExportArchive(base_dir=str(root))

    with pytest.raises(PermissionError):
        archive.read_export("../exports-private/secret.md")


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["../outside/secrets.env", "/proc/self/environ"])
async def test_export_endpoint_404s_for_traversal(
    client, monkeypatch, archive_with_neighbour, name
):
    root, _ = archive_with_neighbour
    monkeypatch.setenv("EXPORT_ARCHIVE_DIR", str(root))

    resp = await client.get("/api/v1/documents/exports", params={"name": name})

    assert resp.status_code == 404
    assert resp.json() == {"detail": "Export not found"}
    assert "SUPPLIER_API_KEY" not in resp.text
