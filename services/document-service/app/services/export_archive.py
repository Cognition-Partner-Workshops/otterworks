"""Reads previously generated export files back out of the export archive.

Exports are rendered to disk by the export worker under ``EXPORT_ARCHIVE_DIR``
(optionally in per-folder subdirectories) and served back to the caller by name.
The caller-supplied name is contained to the archive root: absolute paths,
``..`` segments and symlinks that resolve outside the root are refused as if
the export did not exist, so the route never serves a file the archive does
not own.
"""

from __future__ import annotations

import errno
import os

import structlog

logger = structlog.get_logger()

DEFAULT_ARCHIVE_DIR = "/var/lib/otterworks/exports"
DEFAULT_MAX_BYTES = 10 * 1024 * 1024


class ExportTooLargeError(OSError):
    """The export exceeds the archive's read cap."""


class ExportArchive:
    """Serves rendered export files from the archive directory."""

    def __init__(self, base_dir: str | None = None, max_bytes: int | None = None):
        self.base_dir = base_dir or os.environ.get("EXPORT_ARCHIVE_DIR", DEFAULT_ARCHIVE_DIR)
        self.max_bytes = (
            max_bytes
            if max_bytes is not None
            else int(os.environ.get("EXPORT_ARCHIVE_MAX_BYTES", DEFAULT_MAX_BYTES))
        )

    def resolve(self, name: str) -> str:
        """Return the real path of ``name`` inside the archive root.

        Raises ``FileNotFoundError`` when ``name`` is absolute, contains a ``..``
        or empty segment, or resolves (through symlinks included) to anything
        outside the archive root.
        """
        if not self._is_well_formed(name):
            raise self._outside(name)
        root = os.path.realpath(self.base_dir)
        path = os.path.realpath(os.path.join(root, name))
        if os.path.commonpath([root, path]) != root:
            raise self._outside(name)
        return path

    def read_export(self, name: str) -> str:
        """Return the contents of the named export.

        ``name`` may include a subdirectory (``"reports/q3.md"``). Raises
        ``FileNotFoundError`` when the export does not exist or lies outside
        the archive, and ``ExportTooLargeError`` when it exceeds ``max_bytes``.
        """
        path = self.resolve(name)
        logger.debug("export_read", name=name)
        with open(path, encoding="utf-8") as handle:
            content = handle.read(self.max_bytes + 1)
        if len(content.encode("utf-8")) > self.max_bytes:
            raise ExportTooLargeError(errno.EFBIG, "Export exceeds read cap", name)
        return content

    @staticmethod
    def _is_well_formed(name: str) -> bool:
        if not name or "\x00" in name or os.path.isabs(name):
            return False
        separators = {os.sep, os.altsep} - {None}
        for separator in separators:
            name = name.replace(separator, "/")
        return all(segment not in ("", ".", "..") for segment in name.split("/"))

    @staticmethod
    def _outside(name: str) -> FileNotFoundError:
        logger.warning("export_read_refused", name=name)
        return FileNotFoundError(errno.ENOENT, "No such export", name)
