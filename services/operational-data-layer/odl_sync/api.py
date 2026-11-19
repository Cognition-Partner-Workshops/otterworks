"""Read service with tenant JWT authentication and background synchronization."""

import asyncio
import json
import os
import tempfile
import threading
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

import jwt
import uvicorn
from bson import ObjectId
from bson.decimal128 import Decimal128
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import JSONResponse, Response, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from . import metrics, sync
from .config import Settings
from .parity import write_csv

PREFIX = '/api/v1/odl'


def json_value(value):
    if isinstance(value, Decimal128):
        return str(value.to_decimal())
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.replace(tzinfo=value.tzinfo or timezone.utc).astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, dict):
        return {k: json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    return value


def response(value):
    return JSONResponse(json_value(value))


def page(collection, query, limit, cursor):
    query = dict(query)
    if cursor is not None:
        query['_id'] = {'$gt': cursor}
    items = list(collection.find(query).sort('_id', 1).limit(limit + 1))
    return dict(items=items[:limit], next_cursor=items[limit - 1]['_id'] if len(items) > limit else None)


def required(collection, query):
    doc = collection.find_one(query)
    if doc is None:
        raise HTTPException(404, 'Not found')
    return doc


def report_summary(report):
    result = {key: value for key, value in report.items() if key not in ('tables', '_id')}
    result['tables'] = {}
    for name, table in report.get('tables', {}).items():
        depths = table['depths']
        result['tables'][name] = dict(source=table['source'], depths={key: value['passed'] for key, value in depths.items()},
                                     counts=depths.get('count'), hashes=depths.get('keyed_hash'),
                                     sample_size=depths.get('sampled_values', {}).get('size'),
                                     sample_diff_count=depths.get('sampled_values', {}).get('difference_count'))
    return result


def limited_report(report):
    report.pop('_id', None)
    for table in report.get('tables', {}).values():
        sample = table['depths'].get('sampled_values', {})
        sample.pop('rows', None)
        if 'differences' in sample:
            sample['differences'] = sample['differences'][:100]
    return report


class ReadMetrics:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        started = time.perf_counter()
        status = 500

        async def capture(message):
            nonlocal status
            if message['type'] == 'http.response.start':
                status = message['status']
            await send(message)

        try:
            await self.app(scope, receive, capture)
        finally:
            matched = scope.get('route')
            route = matched.path if matched is not None else 'unmatched'
            if route.startswith(PREFIX):
                route = route[len(PREFIX):] or '/'
            metrics.read_requests.labels(route, str(status)).inc()
            metrics.read_duration.labels(route, str(status)).observe(time.perf_counter() - started)


def sync_loop(settings, stop, interval):
    while not stop.is_set():
        try:
            result = sync.run(settings)
        except Exception as error:
            result = dict(status='failed', error=type(error).__name__)
        print(json.dumps(result, sort_keys=True), flush=True)
        stop.wait(interval)


def ensure_indexes(db):
    db.customers.create_index([('match.status', 1), ('_id', 1)])
    for fields in ([('reason', 1), ('status', 1), ('_id', 1)], [('reason', 1), ('_id', 1)], [('status', 1), ('_id', 1)]):
        db.mapping_exceptions.create_index(fields)
    db.parity_reports.create_index('run_id', unique=True)
    db.parity_reports.create_index([('generated_at', -1)])


def create_app(db=None, settings=None, sync_enabled=True):
    bearer = HTTPBearer(auto_error=False)

    def authorize(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        try:
            if credentials is None:
                raise jwt.InvalidTokenError()
            jwt.decode(credentials.credentials, request.app.state.jwt_secret,
                       algorithms=['HS256', 'HS384', 'HS512'],
                       options={'require': ['exp'], 'verify_aud': False})
        except jwt.InvalidTokenError:
            raise HTTPException(401, 'Invalid or missing bearer token', headers={'WWW-Authenticate': 'Bearer'})

    @asynccontextmanager
    async def lifespan(app):
        client = None
        worker = None
        stop = threading.Event()
        config = settings
        try:
            app.state.jwt_secret = os.environ.get('JWT_SECRET')
            if not app.state.jwt_secret:
                raise ValueError('JWT_SECRET is required')
            if db is None:
                config = config or Settings.environment()
                client = MongoClient(**config.mongo, tz_aware=True)
                app.state.db = client[config.mongo_database]
            else:
                app.state.db = db
            await asyncio.to_thread(ensure_indexes, app.state.db)
            if sync_enabled:
                config = config or Settings.environment()
                interval = float(os.getenv('ODL_SYNC_INTERVAL_SECONDS', '60'))
                if not 0 < interval < float('inf'):
                    raise ValueError('ODL_SYNC_INTERVAL_SECONDS must be finite and positive')
                worker = threading.Thread(target=sync_loop, args=(config, stop, interval), daemon=True)
                worker.start()
            yield
        finally:
            stop.set()
            if worker is not None:
                await asyncio.to_thread(worker.join)
            if client is not None:
                client.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(ReadMetrics)
    router = APIRouter(prefix=PREFIX, dependencies=[Depends(authorize)])

    @app.exception_handler(PyMongoError)
    async def mongo_error(request, error):
        return JSONResponse({'detail': 'Database unavailable'}, status_code=503)

    @app.get('/health')
    def health(request: Request):
        request.app.state.db.command('ping')
        return {'status': 'ok'}

    @app.get('/metrics')
    def prometheus():
        return Response(generate_latest(), headers={'Content-Type': CONTENT_TYPE_LATEST})

    @router.get('/customers')
    def customers(request: Request, db2_cust_no: str | None = Query(None, max_length=10),
                  oracle_account_id: int | None = Query(None, gt=0, lt=2**63),
                  crm_contact_id: str | None = Query(None, max_length=36),
                  match_status: Literal['matched', 'single-source'] | None = None,
                  limit: int = Query(50, ge=1, le=100), cursor: str | None = Query(None, max_length=256)):
        query = {}
        for field, value in (('source_keys.db2_cust_no', db2_cust_no), ('source_keys.oracle_account_ids', oracle_account_id),
                             ('source_keys.crm_contact_id', crm_contact_id), ('match.status', match_status)):
            if value is not None:
                query[field] = value
        return response(page(request.app.state.db.customers, query, limit, cursor))

    @router.get('/customers/{id}')
    def customer(id: str, request: Request):
        return response(required(request.app.state.db.customers, {'_id': id}))

    @router.get('/exceptions')
    def exceptions(request: Request, reason: str | None = Query(None, max_length=80),
                   status: str | None = Query(None, max_length=30), limit: int = Query(50, ge=1, le=100),
                   cursor: str | None = Query(None, max_length=256)):
        query = {key: value for key, value in (('reason', reason), ('status', status)) if value is not None}
        return response(page(request.app.state.db.mapping_exceptions, query, limit, cursor))

    @router.get('/exceptions/{id}')
    def exception(id: str, request: Request):
        return response(required(request.app.state.db.mapping_exceptions, {'_id': id}))

    @router.get('/parity')
    def parity_list(request: Request, limit: int = Query(20, ge=1, le=100)):
        reports = request.app.state.db.parity_reports.find().sort([('generated_at', -1), ('run_id', -1)]).limit(limit)
        return response({'items': [report_summary(report) for report in reports]})

    @router.get('/parity/latest')
    def parity_latest(request: Request):
        report = request.app.state.db.parity_reports.find_one(sort=[('generated_at', -1), ('run_id', -1)])
        if report is None:
            raise HTTPException(404, 'Not found')
        return response(report_summary(report))

    @router.get('/parity/{run_id}.csv')
    def parity_csv(run_id: str, request: Request):
        report = required(request.app.state.db.parity_reports, {'run_id': run_id})
        output = tempfile.SpooledTemporaryFile(mode='w+', max_size=1024 * 1024, newline='')
        try:
            write_csv(report, output)
            output.seek(0)
        except Exception:
            output.close()
            raise

        def stream():
            try:
                while chunk := output.read(65536):
                    yield chunk
            finally:
                output.close()
        return StreamingResponse(stream(), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="odl-parity.csv"'})

    @router.get('/parity/{run_id}')
    def parity_report(run_id: str, request: Request):
        return response(limited_report(required(request.app.state.db.parity_reports, {'run_id': run_id})))

    app.include_router(router)
    return app


app = create_app()


def main():
    uvicorn.run(app, host=os.getenv('ODL_HOST', '0.0.0.0'), port=int(os.getenv('ODL_PORT', '8098')))


if __name__ == '__main__':
    main()
