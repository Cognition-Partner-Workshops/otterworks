"""Execute original audit mappings in rollback-only PostgreSQL isolation."""
from collections import Counter
from pathlib import Path
import tempfile
import uuid

import psycopg
from psycopg import sql

from etl.informatica.runner.db import Connection
from etl.informatica.runner.engine import MappingRun
from etl.informatica.runner.repo import Repository
from etl.informatica.runner.sesslog import Log
from . import local_audit as audit


class IsolatedConnection(Connection):
    def __init__(self, connection, schema):
        super().__init__('AUDIT_PARITY', {'default_database': schema})
        self._conn = connection

    def resolve_table(self, owner, table):
        return super().resolve_table(self.default_database, table)


def materialize(before, after, dsn, ready, business_date, landing_dir=None):
    errors, evidence = {}, {}
    targets = ['AUDIT_PC.' + name for name in audit.PC_TABLES]
    work = audit.ROOT / 'migration/dw-exit/.runs/audit-powercenter'
    work.mkdir(parents=True, exist_ok=True)
    try:
        after.execute('CREATE SCHEMA AUDIT_PC')
        before.execute('CREATE SCHEMA SFX_AUDIT_PC')
        for name in audit.PC_TABLES:
            after.execute('CREATE TABLE AUDIT_PC.' + name + ' AS SELECT * FROM AUDIT.' + name + ' WHERE FALSE')
            before.execute('CREATE TABLE SFX_AUDIT_PC.' + name + ' AS SELECT * FROM SFX_AUDIT.' + name + ' WHERE FALSE')
        after.execute('CREATE SEQUENCE AUDIT_PC.SUMMARY_SEQ START 50001')
        repo = Repository(str(audit.ROOT / 'etl/informatica/repository/SFX_AUDIT'))
        schema = 'audit_parity_' + uuid.uuid4().hex
        with tempfile.TemporaryDirectory(dir=work) as directory, psycopg.connect(dsn) as source:
            source.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
            for name in audit.PC_TABLES:
                source.execute(sql.SQL('CREATE TABLE {}.{} (LIKE sfx_audit.{} INCLUDING ALL)').format(
                    sql.Identifier(schema), sql.Identifier(name.lower()), sql.Identifier(name.lower())))
            connection = IsolatedConnection(source, schema)
            process_vars = {'$PMSourceFileDir': str(landing_dir or audit.ROOT / 'warehouse/landing'),
                            '$PMStorageDir': directory, '$PMBadFileDir': directory}
            params = {'$DBConnection_SRC': 'AUDIT_PARITY', '$DBConnection_TGT': 'AUDIT_PARITY',
                      '$$LOAD_DATE': business_date}
            for name in audit.PC_TABLES:
                session_name = 's_m_SFX_' + name
                session = repo.sessions[('SFX_AUDIT', session_name)]
                log = Log(str(Path(directory) / (session_name + '.log')))
                run = MappingRun(repo, session, params, process_vars, {'AUDIT_PARITY': connection}, log)
                stats = run.run()
                evidence[session_name] = {'rows_read': stats.rows_read, 'rows_written': stats.rows_written,
                                          'rows_rejected': stats.rows_rejected, 'first_error': stats.first_error,
                                          'log': log.lines}
            audit.execute(after, 'CALL __RUN_DATABASE__.AUDIT_PC.WF_SFX_AUDIT_DAILY();', business_date)
            for name in audit.PC_TABLES:
                rows = source.execute(sql.SQL('SELECT * FROM {}.{}').format(
                    sql.Identifier(schema), sql.Identifier(name.lower()))).fetchall()
                if rows:
                    before.executemany('INSERT INTO SFX_AUDIT_PC.' + name + ' VALUES (' +
                                       ','.join('?' for _ in rows[0]) + ')', rows)
                ready.add('AUDIT_PC.' + name)
            old = before.execute('SELECT SUMMARY_DT,CUSTOMER_ID,EVENT_COUNT,EXPORT_COUNT FROM SFX_AUDIT_PC.AUDIT_DAILY_SUMMARY').fetchall()
            new = after.execute('SELECT SUMMARY_DT,CUSTOMER_ID,EVENT_COUNT,EXPORT_COUNT FROM AUDIT_PC.AUDIT_DAILY_SUMMARY').fetchall()
            evidence['summary_non_identity_multiset_matches'] = Counter(old) == Counter(new)
            source.rollback()
        evidence['isolation'] = 'fresh empty targets and sequence state; temporary schema rolled back; same landing PSVs'
    except Exception as error:
        for target in targets:
            ready.discard(target)
            errors[target] = 'PowerCenter audit proof failed: ' + type(error).__name__ + ': ' + str(error)
    return errors, evidence
