import sys

import pytest

from warehouse.process import executable


def test_interpreter_path_is_preserved():
    assert executable(sys.executable, r'python(?:[0-9]+(?:\.[0-9]+)*)?') == sys.executable


def test_path_with_spaces_is_preserved(tmp_path):
    directory = tmp_path / 'venv with spaces'
    directory.mkdir()
    python = directory / 'python3'
    python.touch()
    python.chmod(0o755)
    assert executable(str(python), r'python3') == str(python)


@pytest.mark.parametrize('value', ['', 'python3;touch injected', 'python3 -c code', '$(python3)', '/bin/sh'])
def test_invalid_interpreter_paths(value):
    with pytest.raises(ValueError):
        executable(value, r'python(?:[0-9]+(?:\.[0-9]+)*)?')


def test_missing_interpreter_path(tmp_path):
    with pytest.raises(ValueError, match='executable file'):
        executable(str(tmp_path / 'python3'), r'python3')
