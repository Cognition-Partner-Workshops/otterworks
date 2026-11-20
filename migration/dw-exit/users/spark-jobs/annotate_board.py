"""Record group-specific input provenance after the shared board command."""
import json
import os
from pathlib import Path


def annotate(path):
    board = json.loads(path.read_text())
    board['measurement_contract']['source'] = 'Legacy Spark fixture PSV inputs; unmodified legacy Spark job bodies'
    board['measurement_contract']['fixture'] = {
        'generator': 'etl/spark/fixture/generate_fixture.py',
        'schemas': 'etl/spark/jobs/py/common/schemas.py',
        'seed': 1110,
        'rows_per_table': int(os.environ.get('BOARD_ROWS', '200')),
        'target_inputs': 'USERS.SPARK_FIXTURE_*',
    }
    for row in board['rows']:
        provenance = 'Shared input: legacy Spark fixture generator, seed=1110; same PSV rows on both sides.'
        if row['status'] == 'green':
            row['reason'] = 'Measured equal. ' + provenance
        elif provenance not in (row.get('reason') or ''):
            row['reason'] = (row.get('reason') or '') + ' ' + provenance
    path.write_text(json.dumps(board, indent=2) + '\n')


if __name__ == '__main__':
    annotate(Path(__file__).with_name('board.json'))
