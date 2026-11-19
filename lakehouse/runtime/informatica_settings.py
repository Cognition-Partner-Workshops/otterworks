"""PowerCenter parameter scopes retained independently of connection transport."""

import configparser
from pathlib import Path

from .ingest import business_date


DEFAULT = Path(__file__).with_name('informatica.par')


def resolve(folder, workflow, session=None, *, path=DEFAULT, day=None):
    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str
    with Path(path).open() as handle:
        try:
            config.read_file(handle)
        except configparser.Error as exc:
            raise ValueError('Malformed Informatica parameters') from exc
    scope = f'{folder}.WF:{workflow}'
    ranks = {'GLOBAL': 0, scope.upper(): 1}
    if session:
        ranks[(scope + '.ST:' + session).upper()] = 2
        ranks[(folder + '.ST:' + session).upper()] = 2
        ranks[(scope + '.WT:' + session).upper()] = 2
    layers = [(ranks[name.upper()], name) for name in config.sections() if name.upper() in ranks]
    values = {}
    for _, name in sorted(layers, key=lambda layer: layer[0]):
        values.update(config[name])
    if day is not None:
        business_date(day)
        values['$$LOAD_DATE'] = day
    return values
