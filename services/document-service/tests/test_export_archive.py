"""Tests for the export archive reader."""

import pytest

from app.services import export_archive
from app.services.export_archive import ExportArchive, ExportTooLargeError


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
    secret.write_text("SUPPLIER_API_KEY=sk-fixture-not-a-real-key\n", encoding="utf-8")
    return secret


TRAVERSAL_NAMES = (
    "../outside/tenant-secrets.env",
    "reports/../../outside/tenant-secrets.env",
    "../../../../../../etc/passwd",
    "/etc/passwd",
    "/proc/self/environ",
    "reports//../q3.md",
    "./report.md",
    "report.md\x00.txt",
)


@pytest.mark.parametrize("name", TRAVERSAL_NAMES)
def test_rejects_names_that_leave_the_archive(archive, outside_file, name):
    name = name.replace("outside", outside_file.parent.name)
    with pytest.raises(FileNotFoundError):
        archive.read_export(name)


def test_absolute_path_inside_archive_is_still_rejected(archive, tmp_path):
    with pytest.raises(FileNotFoundError):
        archive.read_export(str(tmp_path / "report.md"))


def test_symlink_pointing_outside_archive_is_rejected(archive, tmp_path, outside_file):
    (tmp_path / "escape.env").symlink_to(outside_file)
    with pytest.raises(FileNotFoundError):
        archive.read_export("escape.env")


def test_symlinked_archive_root_still_serves_exports(tmp_path):
    real_root = tmp_path / "real"
    real_root.mkdir()
    (real_root / "report.md").write_text("# Report\n", encoding="utf-8")
    link_root = tmp_path / "link"
    link_root.symlink_to(real_root, target_is_directory=True)

    assert ExportArchive(base_dir=str(link_root)).read_export("report.md") == "# Report\n"


def test_oversized_export_is_refused(tmp_path):
    (tmp_path / "big.md").write_text("x" * 64, encoding="utf-8")

    with pytest.raises(ExportTooLargeError):
        ExportArchive(base_dir=str(tmp_path), max_bytes=32).read_export("big.md")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name",
    ["../outside/tenant-secrets.env", "/proc/self/environ", "../../../../etc/passwd"],
)
async def test_export_endpoint_404s_for_traversal(
    client, monkeypatch, tmp_path, outside_file, name
):
    monkeypatch.setenv("EXPORT_ARCHIVE_DIR", str(tmp_path))
    name = name.replace("outside", outside_file.parent.name)

    resp = await client.get("/api/v1/documents/exports", params={"name": name})

    assert resp.status_code == 404
    assert "SUPPLIER_API_KEY" not in resp.text
    assert "root:x:0:0" not in resp.text


@pytest.mark.asyncio
async def test_export_endpoint_404s_for_encoded_traversal(client, monkeypatch, tmp_path):
    monkeypatch.setenv("EXPORT_ARCHIVE_DIR", str(tmp_path))

    resp = await client.get("/api/v1/documents/exports?name=..%2f..%2f..%2f..%2fetc%2fpasswd")

    assert resp.status_code == 404
    assert "root:x:0:0" not in resp.text


@pytest.mark.asyncio
async def test_export_endpoint_413s_for_oversized_export(client, monkeypatch, tmp_path):
    (tmp_path / "big.md").write_text("x" * 64, encoding="utf-8")
    monkeypatch.setenv("EXPORT_ARCHIVE_DIR", str(tmp_path))
    monkeypatch.setenv("EXPORT_ARCHIVE_MAX_BYTES", "32")

    resp = await client.get("/api/v1/documents/exports", params={"name": "big.md"})

    assert resp.status_code == 413
