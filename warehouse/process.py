"""Validation for configured executable paths."""

import os
from pathlib import Path
import re


def executable(value, name_pattern):
    if (not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_./ -]+', value)
            or not re.fullmatch(name_pattern, Path(value).name)):
        raise ValueError('Invalid executable path')
    if '/' in value and (not Path(value).is_file() or not os.access(value, os.X_OK)):
        raise ValueError('Executable path must name an executable file')
    return value
