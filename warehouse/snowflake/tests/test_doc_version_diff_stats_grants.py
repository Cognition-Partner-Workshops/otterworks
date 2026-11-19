"""The document refresh must retain explicit consumer grants on replacement."""

import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[3]))
from warehouse.run_config import render as _run_render

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock


def test_overwrite_copies_existing_grants():
    path = Path(__file__).resolve().parents[2] / 'snowpark/doc_version_diff_stats.py'
    spec = importlib.util.spec_from_file_location('doc_diff_job', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    session = MagicMock()
    session.get_current_database.return_value = _run_render('"__RUN_DATABASE__"')
    writer = session.table.return_value.with_column.return_value.select.return_value.write
    module.run(session)
    module.run(session)
    assert writer.save_as_table.call_count == 2
    for call in writer.save_as_table.call_args_list:
        assert call.args[0] == [_run_render('"__RUN_DATABASE__"'), 'MART_SPARK', 'DOC_VERSION_DIFF_STATS']
        assert call.kwargs['mode'] == 'overwrite'
        assert call.kwargs.get('copy_grants') is True
