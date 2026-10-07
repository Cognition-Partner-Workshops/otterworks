"""Reads previously generated export files back out of the export archive.

Exports are rendered to disk by the export worker under ``EXPORT_ARCHIVE_DIR``
(optionally in per-folder subdirectories) and served back to the caller by name.
"""

from __future__ import annotations

import os

import structlog

logger = structlog.get_logger()

DEFAULT_ARCHIVE_DIR = "/var/lib/otterworks/exports"


class ExportArchive:
    """Serves rendered export files from the archive directory."""

    def __init__(self, base_dir: str | None = None):
        self.base_dir = base_dir or os.environ.get(
            "EXPORT_ARCHIVE_DIR", DEFAULT_ARCHIVE_DIR
        )

    def read_export(self, name: str) -> str:
        """Return the contents of the named export.

        ``name`` may include a subdirectory (``"reports/q3.md"``). The resolved
        path (symlinks and ``..`` included) must stay inside the resolved archive
        root. Raises ``FileNotFoundError`` when the export does not exist or the
        name resolves outside the archive.
        """
        root = os.path.realpath(self.base_dir)
        try:
            path = os.path.realpath(os.path.join(root, name))
        except ValueError as exc:
            raise FileNotFoundError(f"Export not found: {name!r}") from exc
        if os.path.commonpath([root, path]) != root:
            logger.warning("export_read_outside_archive", name=name)
            raise FileNotFoundError(f"Export not found: {name!r}")
        logger.debug("export_read", name=name)
        with open(path, encoding="utf-8") as handle:
            return handle.read()
