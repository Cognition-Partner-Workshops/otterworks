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
def secret_outside_archive(tmp_path):
    archive_dir = tmp_path / "archive"
    (archive_dir / "reports").mkdir(parents=True)
    (archive_dir / "report.md").write_text("# Report\n", encoding="utf-8")
    secret = tmp_path / "outside" / "tenant-secrets.env"
    secret.parent.mkdir()
    secret.write_text("SUPPLIER_API_KEY=fixture\n", encoding="utf-8")
    return archive_dir, secret


@pytest.mark.parametrize(
    "name",
    [
        "../outside/tenant-secrets.env",
        "reports/../../outside/tenant-secrets.env",
        "/etc/passwd",
        "../../../../../../etc/passwd",
        "..",
        ".",
        "report.md\x00",
    ],
)
def test_rejects_names_that_escape_the_archive(secret_outside_archive, name):
    archive_dir, _ = secret_outside_archive
    with pytest.raises(FileNotFoundError):
        ExportArchive(base_dir=str(archive_dir)).read_export(name)


def test_rejects_absolute_path_inside_the_archive(secret_outside_archive):
    archive_dir, _ = secret_outside_archive
    with pytest.raises(FileNotFoundError):
        ExportArchive(base_dir=str(archive_dir)).read_export(str(archive_dir / "report.md"))


def test_rejects_symlink_pointing_outside_the_archive(secret_outside_archive):
    archive_dir, secret = secret_outside_archive
    (archive_dir / "link.env").symlink_to(secret)
    with pytest.raises(FileNotFoundError):
        ExportArchive(base_dir=str(archive_dir)).read_export("link.env")


def test_allows_dot_segments_that_stay_inside_the_archive(secret_outside_archive):
    archive_dir, _ = secret_outside_archive
    archive = ExportArchive(base_dir=str(archive_dir))
    assert archive.read_export("reports/../report.md") == "# Report\n"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name",
    [
        "../outside/tenant-secrets.env",
        "/etc/passwd",
        "../../../../../../etc/passwd",
        "/proc/self/environ",
        "report.md\x00",
    ],
)
async def test_export_endpoint_404s_for_traversal(
    client, monkeypatch, secret_outside_archive, name
):
    archive_dir, _ = secret_outside_archive
    monkeypatch.setenv("EXPORT_ARCHIVE_DIR", str(archive_dir))

    resp = await client.get("/api/v1/documents/exports", params={"name": name})

    assert resp.status_code == 404
    assert "SUPPLIER_API_KEY" not in resp.text
    assert "root:" not in resp.text
