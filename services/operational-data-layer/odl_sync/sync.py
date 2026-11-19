import argparse
import json
import time
from collections import Counter

from prometheus_client import start_http_server
from pymongo import MongoClient

from . import metrics
from .config import Settings
from .extract import ExtractError
from .extract import db2, oracle, postgres
from .load import load
from .merge import merge


def run(settings):
    extracts = []
    failures = {}
    for module in (db2, oracle, postgres):
        source = module.__name__.rsplit('.', 1)[-1]
        try:
            result = module.extract(settings)
            extracts.append(result)
            if any(e['reason'] == 'transform_failed' for e in result.unplaced):
                metrics.errors.labels(source, 'transform').inc()
        except ExtractError as error:
            metrics.errors.labels(source, error.reason).inc()
            failures[source] = error.reason
        except Exception:
            metrics.errors.labels(source, 'transform').inc()
            failures[source] = 'transform'
    if failures:
        return dict(status='skipped', failures=failures)
    customers, exceptions = merge(extracts)
    try:
        with MongoClient(**settings.mongo) as client:
            result = load(client[settings.mongo_database], customers, exceptions)
    except Exception as error:
        for source in metrics.SOURCES:
            metrics.errors.labels(source, 'write').inc()
        return dict(status='failed', failures={'write': type(error).__name__})
    for extract in extracts:
        metrics.success(extract.source, extract.checkpoint, result['applied'][extract.source])
    return dict(status='ok', documents_by_status=dict(Counter(d['match']['status'] for d in customers)),
                exceptions_by_reason=dict(Counter(e['reason'] for e in exceptions)), **result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--interval', type=float, default=60)
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error('--interval must be positive')
    settings = Settings.environment()
    if not args.once:
        start_http_server(9108)
    while True:
        result = run(settings)
        print(json.dumps(result, sort_keys=True), flush=True)
        if args.once:
            raise SystemExit(0 if result['status'] == 'ok' else 1)
        time.sleep(args.interval)


if __name__ == '__main__':
    main()
