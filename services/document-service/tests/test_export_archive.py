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
def secret_outside(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "tenant-secrets.env").write_text("JWT_SECRET=marker\n", encoding="utf-8")
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    (archive_dir / "report.md").write_text("# Report\n", encoding="utf-8")
    (archive_dir / "reports").mkdir()
    (archive_dir / "reports" / "q3.md").write_text("# Q3\n", encoding="utf-8")
    return archive_dir, outside / "tenant-secrets.env"


TRAVERSAL_NAMES = [
    "../outside/tenant-secrets.env",
    "reports/../../outside/tenant-secrets.env",
    "../../../../../../etc/passwd",
    "/etc/passwd",
    "/proc/self/environ",
    "//etc/passwd",
    ".",
    "reports/..",
    "report.md\x00.txt",
]


@pytest.mark.parametrize("name", TRAVERSAL_NAMES)
def test_rejects_names_outside_the_archive(secret_outside, name):
    archive_dir, _ = secret_outside
    with pytest.raises(FileNotFoundError):
        ExportArchive(base_dir=str(archive_dir)).read_export(name)


def test_rejects_absolute_path_into_the_archive(secret_outside):
    archive_dir, _ = secret_outside
    with pytest.raises(FileNotFoundError):
        ExportArchive(base_dir=str(archive_dir)).read_export(str(archive_dir / "report.md"))


def test_rejects_symlink_escaping_the_archive(secret_outside):
    archive_dir, secret = secret_outside
    (archive_dir / "link.env").symlink_to(secret)
    with pytest.raises(FileNotFoundError):
        ExportArchive(base_dir=str(archive_dir)).read_export("link.env")


def test_allows_dotdot_that_stays_inside_the_archive(secret_outside):
    archive_dir, _ = secret_outside
    archive = ExportArchive(base_dir=str(archive_dir))
    assert archive.read_export("reports/../report.md") == "# Report\n"
    assert archive.read_export("./reports/q3.md") == "# Q3\n"


@pytest.mark.asyncio
@pytest.mark.parametrize("name", TRAVERSAL_NAMES)
async def test_export_endpoint_404s_for_traversal(client, monkeypatch, secret_outside, name):
    archive_dir, _ = secret_outside
    monkeypatch.setenv("EXPORT_ARCHIVE_DIR", str(archive_dir))

    resp = await client.get("/api/v1/documents/exports", params={"name": name})

    assert resp.status_code == 404
    assert "marker" not in resp.text
    assert "root:" not in resp.text


@pytest.mark.asyncio
async def test_export_endpoint_still_serves_subdirectory_export(
    client, monkeypatch, secret_outside
):
    archive_dir, _ = secret_outside
    monkeypatch.setenv("EXPORT_ARCHIVE_DIR", str(archive_dir))

    resp = await client.get("/api/v1/documents/exports", params={"name": "reports/q3.md"})

    assert resp.status_code == 200
    assert resp.text == "# Q3\n"
