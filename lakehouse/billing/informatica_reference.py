"""Run the estate's actual emulator in an isolated database, never its live targets."""

import argparse
import json
import os
import re
import zlib
from pathlib import Path

import psycopg
from psycopg import sql

from etl.informatica.runner.repo import Repository
from etl.informatica.runner.workflow import Integration
from etl.informatica.runner import workflow
from etl.informatica.runner.engine import MappingRun
from lakehouse.billing.informatica import BASE, ORDER, TARGETS, delta, output, save
from lakehouse.orchestration.graph import business_date
from lakehouse.parity.readers import postgres_connection
from lakehouse.runtime.layout import ROOT, data_root
from lakehouse.runtime.session import create_session


class CapturedMapping(MappingRun):
    captures = {}

    def t_expression(self, name, transformation):
        before = list(self._upstream_stream(name))
        fields = [p for p in transformation.fields if p.is_input]
        binding = self._bind(name, fields)
        defaults = self._input_defaults(fields)
        inputs = {id(ctx): self._read_inputs(ctx, binding, defaults) for ctx in before}
        super().t_expression(name, transformation)
        after = {id(ctx) for ctx in self._upstream_stream(name)}
        self.captures.setdefault(self.mapping.name, []).extend(
            {'stage': name, 'row': inputs[id(ctx)]} for ctx in before if id(ctx) not in after)


def prepare(landing, day):
    business_date(day)
    legacy = os.environ.get('LEGACY_NS', 'sfx-d1110-before')
    if not os.environ.get('TD_PG_DSN'):
        os.environ.setdefault('TD_PG_PORT', str(54500 + zlib.crc32(legacy.encode()) % 1000))
    root = data_root() / 'informatica' / day
    manifest = json.loads((root / 'inputs.json').read_text())
    prior = json.loads((root / 'inputs/prior.json').read_text())
    database = 'lh_billing_infa_' + str(zlib.crc32(os.environ['NS'].encode()))
    reference = root / 'reference'
    with postgres_connection() as source:
        source.autocommit = True
        exists = source.execute('SELECT 1 FROM pg_database WHERE datname=%s', (database,)).fetchone()
        if not exists:
            source.execute(sql.Composed([sql.SQL('CREATE DATABASE '), sql.Identifier(database)]))
        connection = source.info.get_parameters()
        connection['password'] = source.info.password
        connection['dbname'] = database
        with psycopg.connect(**connection, autocommit=True) as target:
            target.execute('CREATE SCHEMA IF NOT EXISTS sfx_billing')
            for table in BASE:
                name = table.lower()
                attributes = source.execute('''SELECT a.attname, format_type(a.atttypid,a.atttypmod), a.attnotnull
                    FROM pg_attribute a WHERE a.attrelid=to_regclass(%s) AND a.attnum>0 AND NOT a.attisdropped
                    ORDER BY a.attnum''', ('sfx_billing.' + name,)).fetchall()
                if not attributes:
                    raise RuntimeError('Missing baseline table: ' + name)
                identity = sql.Identifier('sfx_billing', name)
                target.execute(sql.Composed([sql.SQL('DROP TABLE IF EXISTS '), identity]))
                definitions = [sql.SQL('{} {}{}').format(sql.Identifier(n), sql.SQL(t),
                                   sql.SQL(' NOT NULL' if required else '')) for n, t, required in attributes]
                constraints = source.execute('SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid=to_regclass(%s)',
                                             ('sfx_billing.' + name,)).fetchall()
                definitions += [sql.SQL(c[0]) for c in constraints]
                target.execute(sql.Composed([sql.SQL('CREATE TABLE '), identity, sql.SQL(' ('),
                                             sql.SQL(',').join(definitions), sql.SQL(')')]))
                rows = [tuple(row.get(a[0]) for a in attributes) for row in prior[table]]
                with target.cursor().copy(sql.SQL('COPY {} FROM STDIN').format(identity)) as copy:
                    for row in rows:
                        copy.write_row(row)
        os.environ.update(TD_HOST=source.info.host, TD_PORT=str(source.info.port), TD_DB=database,
                          TD_USER=source.info.user, TD_PASSWORD=source.info.password or '', LANDING_DIR=str(Path(landing).resolve()))
        reference.mkdir(parents=True, exist_ok=True)
        parameters = (ROOT.parent / 'etl/informatica/params/sfx_d1110_daily.par').read_text()
        parameters, overrides = re.subn(r'(?m)^\$\$LOAD_DATE=.*$', '$$LOAD_DATE=' + day, parameters)
        if overrides != 1:
            raise RuntimeError('Expected one Global LOAD_DATE parameter')
        parameter_file = reference / 'parameters.par'
        parameter_file.write_text(parameters)
        save(reference / 'Storage/sequence_values.json', {
            'SFX_BILLING.m_SFX_GL_JOURNAL_LINE.SEQ_GL_JOURNAL_LINE': manifest['sequence_start']})
        integration = Integration(Repository(str(ROOT.parent / 'etl/informatica/repository/SFX_BILLING')),
                                  [str(parameter_file)], pmrootdir=str(reference))
        for old in (reference / 'BadFiles').glob('*.bad'):
            old.unlink()
        CapturedMapping.captures = {}
        workflow.MappingRun = CapturedMapping
        try:
            status, results = integration.run_workflow('SFX_BILLING', 'wf_SFX_BILLING_DAILY')
        finally:
            workflow.MappingRun = MappingRun
        save(reference / 'workflow_result.json', {'status': status, 'sessions': results})
        spark = create_session()
        with psycopg.connect(**connection) as target:
            for table in ORDER:
                rows = target.execute(sql.Composed([sql.SQL('SELECT * FROM '),
                                                    sql.Identifier('sfx_billing', table.lower())]))
                names = [c.name.lower() for c in rows.description]
                char_fields = {f.get('NAME').lower() for f in TARGETS[table] if f.get('DATATYPE') == 'char'}
                values = [{k: v.rstrip(' ') if k in char_fields and isinstance(v, str) else v
                           for k, v in zip(names, row)} for row in rows.fetchall()]
                record = next((r for r in results.values() if r['MAPPING_NAME'] == 'm_SFX_' + table), None)
                rejected = []
                session = integration.repo.sessions['SFX_BILLING', 's_m_SFX_' + table]
                for extension in session.extensions:
                    if extension.type != 'WRITER':
                        continue
                    bad = reference / 'BadFiles' / extension.attrs['Reject filename']
                    if bad.exists():
                        rejected += [{'target': extension.sinstance, 'record': line} for line in bad.read_text().splitlines()]
                errors = CapturedMapping.captures.get('m_SFX_' + table, [])
                if record and len(errors) != int(record['FAILED_SOURCE_ROWS']):
                    raise RuntimeError('Uncaptured source/transform errors for ' + table)
                output(reference, table, values, rejected, errors)
                delta(spark, reference, table, values)
                print(f'Reference {table}: {len(values)} rows, {len(rejected)} writer rejects, {len(errors)} transformation errors', flush=True)
        spark.stop()
        if status != 'SUCCEEDED':
            raise RuntimeError('Legacy Informatica workflow failed; see reference/workflow_result.json')
    print('Informatica reference: PASS (actual emulator; isolated database ' + database + ')')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--business-date', required=True)
    parser.add_argument('--landing', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.landing, args.business_date)


if __name__ == '__main__':
    main()
