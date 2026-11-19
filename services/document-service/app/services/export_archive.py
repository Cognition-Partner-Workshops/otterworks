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

        ``name`` may include a subdirectory (``"reports/q3.md"``). Raises
        ``FileNotFoundError`` when the export does not exist.
        """
        path = os.path.join(self.base_dir, name)
        requested = os.fspath(name)
        components = requested.replace(os.altsep, os.sep) if os.altsep else requested
        if os.path.isabs(requested) or ".." in components.split(os.sep):
            raise FileNotFoundError(2, os.strerror(2), path)
        archive_root = os.path.realpath(self.base_dir)
        resolved = os.path.realpath(path)
        if os.path.commonpath((archive_root, resolved)) != archive_root:
            raise FileNotFoundError(2, os.strerror(2), path)
        logger.debug("export_read", name=name)
        try:
            with open(resolved, encoding="utf-8") as handle:
                return handle.read()
        except OSError as exc:
            if exc.filename is not None:
                exc.filename = path
            raise
