import csv
import datetime
from decimal import Decimal
import hashlib
import json
import os
import re
import sys
from pathlib import Path

import psycopg
import sqlglot
from sqlglot import exp
from sqlglot.transforms import eliminate_qualify

from .parser import commands, split


ERRORS = {'42P01': 3807, '42704': 3807, '42P07': 3803, '3F000': 3802,
          '23505': 2801, '42601': 3706, '22007': 2666, '22008': 2620,
          '22003': 2616, '42501': 3524, '22P02': 2620}


def literal(value):
    if value is None:
        return 'NULL'
    if isinstance(value, datetime.datetime):
        return "TIMESTAMP '" + value.isoformat(sep=' ') + "'"
    if isinstance(value, datetime.date):
        return "DATE '" + value.isoformat() + "'"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


class Runner:
    def __init__(self, connection=None, variables=None, output=None):
        dsn = os.environ.get('TD_PG_DSN', '')
        self.conn = connection or psycopg.connect(dsn, **{
            k: os.environ.get('TD_PG_' + v, default) for k, v, default in [
                ('host', 'HOST', 'localhost'), ('port', 'PORT', '5432'),
                ('dbname', 'DB', 'teradata'), ('user', 'USER', 'postgres'),
                ('password', 'PASSWORD', '')] if not dsn or 'TD_PG_' + v in os.environ})
        self.conn.autocommit = True
        self.conn.execute(Path(__file__).with_name('bootstrap.sql').read_text())
        self.conn.execute('SET search_path TO public,sfx_td')
        self.variables = {**os.environ, **(variables or {})}
        self.output = output or sys.stdout
        self.errorcode = self.activitycount = self.errorlevel = 0
        self.sqlstate = '00000'
        self.rows, self.headers, self.settings = [], [], {}
        self.export = self.import_file = None
        self.repeat = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.conn.close()

    def say(self, message):
        print(message, file=self.output)

    def run(self, text):
        text = re.sub(r'\$\{(\w+)\}', lambda m: self.variables.get(m[1], m[0]), text)
        items = list(commands(text))
        i = 0
        while i < len(items):
            item = items[i]
            if item.startswith('.'):
                action = self.dot(item)
                if action and action[0] == 'quit':
                    return action[1]
                if action and action[0] == 'goto':
                    target = '.LABEL ' + action[1].upper()
                    found = next((j for j in range(i + 1, len(items)) if items[j].upper() == target), None)
                    if found is None:
                        self.say('*** Failure 3706 Label not found forward: ' + action[1])
                        return 3706
                    i = found
            elif self.repeat and self.import_file:
                start = item.index('(')
                depth, end = 1, start + 1
                while depth:
                    depth += (item[end] == '(') - (item[end] == ')')
                    end += 1
                names = [x.strip().split()[0] for x in split(item[start + 1:end - 1], ',')]
                with open(self.import_file, newline='') as handle:
                    for row in csv.reader(handle, delimiter=self.settings.get('import_separator', '|')):
                        values = dict(zip(names, row))
                        self.execute(re.sub(r':(\w+)', lambda m: literal(values[m[1]]), item[end:].strip()))
                self.repeat = False
            else:
                self.execute(item)
            i += 1
        return 0

    def dot(self, command):
        name, _, rest = command[1:].partition(' ')
        name, rest = name.upper(), rest.strip()
        if name in ('QUIT', 'EXIT'):
            return ('quit', int(rest or 0))
        if name == 'GOTO':
            return ('goto', rest)
        if name == 'IF':
            m = re.fullmatch(r'(ERRORCODE|ACTIVITYCOUNT|ERRORLEVEL)\s*(<>|!=|>=|<=|=|>|<)\s*(\d+)\s+THEN\s+(.*)', rest, re.I)
            if not m:
                raise ValueError('Invalid .IF: ' + rest)
            a, b = getattr(self, m[1].lower()), int(m[3])
            if {'=': a == b, '<>': a != b, '!=': a != b, '>': a > b, '<': a < b, '>=': a >= b, '<=': a <= b}[m[2]]:
                return self.dot(m[4])
        elif name == 'SET':
            key, _, value = rest.partition(' ')
            self.settings[key.upper()] = value.strip("'\"")
            if key.upper() not in {'WIDTH', 'SEPARATOR', 'TITLEDASHES', 'ERRORLEVEL', 'ERROROUT', 'RETLIMIT', 'QUIET', 'ECHOREQ'}:
                self.say('*** Warning: unknown setting ' + key)
        elif name == 'EXPORT':
            if rest.upper() == 'RESET':
                self.export = None
            else:
                m = re.match(r'(REPORT|DATA)\s+FILE\s*=\s*[\'\"]?([^\'\"]+)', rest, re.I)
                self.export = (m[1].upper(), Path(m[2].strip()))
                self.export[1].write_text('')
        elif name == 'IMPORT':
            m = re.match(r"VARTEXT\s+'(.)'\s+FILE\s*=\s*['\"]?([^'\"]+)", rest, re.I)
            self.settings['import_separator'], self.import_file = m[1], m[2].strip()
        elif name == 'REPEAT':
            self.repeat = True
        elif name == 'RUN':
            returncode = self.run(Path(re.sub(r'^FILE\s*=\s*', '', rest, flags=re.I).strip("'\"")).read_text())
            if returncode:
                return ('quit', returncode)
        elif name not in {'IF', 'LOGON', 'LOGOFF', 'LABEL', 'REMARK'}:
            self.say('*** Warning: unsupported command ' + name)

    def execute(self, source):
        self.errorcode = self.errorlevel = self.activitycount = 0
        self.sqlstate = '00000'
        self.rows, self.headers = [], []
        try:
            if self.routine(source):
                return
            statement, after = self.translate(source)
            if not statement:
                return
            cur = self.conn.execute(statement)
            self.activitycount = max(cur.rowcount, 0)
            if cur.description:
                self.headers = [c.name for c in cur.description]
                self.rows = cur.fetchall()
                self.report_formats = {}
                for table in sqlglot.parse_one(source, read='teradata').find_all(exp.Table):
                    relation = table.copy()
                    relation.set('alias', None)
                    saved = self.conn.execute('SELECT formats FROM sfx_td.tables WHERE name=%s', (self.canonical_name(relation.sql(dialect='postgres').lower()),)).fetchone()
                    if saved:
                        self.report_formats.update(saved[0])
                self.say(f'*** Query completed. {self.activitycount} rows found.')
                self.render()
            else:
                self.say(f'*** {"Insert" if source.upper().startswith(("INSERT", "INS ")) else "Request"} completed. {self.activitycount} rows added.')
            if after:
                after()
        except (psycopg.Error, sqlglot.errors.SqlglotError, ValueError) as exc:
            self.errorcode = ERRORS.get(getattr(exc, 'sqlstate', None), 3706 if isinstance(exc, sqlglot.errors.SqlglotError) else 3700)
            self.errorlevel = 8
            self.sqlstate = getattr(exc, 'sqlstate', None) or '42000'
            self.say(f'*** Failure {self.errorcode} {exc}')

    def render(self):
        separator = self.settings.get('SEPARATOR', '|')
        def formatted(value, name):
            if value is None:
                return ''
            fmt = getattr(self, 'report_formats', {}).get(name)
            if fmt and self.export and self.export[0] == 'REPORT' and hasattr(value, 'strftime'):
                for td, py in [('YYYY', '%Y'), ('MMM', '%b'), ('YY', '%y'), ('MM', '%m'), ('DD', '%d'), ('B', ' ')]:
                    fmt = fmt.replace(td, py)
                return value.strftime(fmt)
            return str(value)
        lines = [separator.join(formatted(v, n) for n, v in zip(self.headers, row)) for row in self.rows]
        if self.export:
            with self.export[1].open('a') as handle:
                handle.write('\n'.join(lines) + ('\n' if lines else ''))
        else:
            self.say(separator.join(self.headers))
            for line in lines:
                self.say(line)

    def columns(self, table):
        return self.conn.execute('''SELECT a.attname,format_type(a.atttypid,a.atttypmod)
            FROM pg_attribute a WHERE a.attrelid=to_regclass(%s) AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum''', (table,)).fetchall()

    def translate(self, source):
        s = source.strip()
        s = re.sub(r'^(SEL|INS|UPD|DEL)\b', lambda m: {'SEL': 'SELECT', 'INS': 'INSERT', 'UPD': 'UPDATE', 'DEL': 'DELETE'}[m[1].upper()], s, flags=re.I)
        if re.match(r'COLLECT\s+STATISTICS', s, re.I):
            return '', None
        if s.upper() in ('BT', 'ET'):
            return ('BEGIN' if s.upper() == 'BT' else 'COMMIT'), None
        m = re.match(r'DATABASE\s+([\w]+)$', s, re.I)
        if m:
            if not self.conn.execute('SELECT 1 FROM pg_namespace WHERE nspname=%s', (m[1].lower(),)).fetchone():
                raise psycopg.errors.InvalidSchemaName('Database does not exist')
            return f'SET search_path TO {m[1]}, public,sfx_td', None
        m = re.match(r'CREATE\s+DATABASE\s+(\w+)', s, re.I)
        if m:
            return 'CREATE SCHEMA ' + m[1], None
        s = re.sub(r'LOCKING\s+ROW\s+FOR\s+ACCESS\s*', '', s, flags=re.I)
        if re.match(r'CREATE\s+(?:(?:SET|MULTISET|VOLATILE)\s+)*TABLE\b', s, re.I):
            return self.create_table(s)
        s = re.sub(r'CAST\(([^()]+)\s+AS\s+FORMAT\s+\'([^\']+)\'\)', r"TO_CHAR(\1, '\2')", s, flags=re.I)
        s = re.sub(r"\((\w+(?:\.\w+)?)\s*\(FORMAT\s+'([^']+)'\)\)", r"TO_CHAR(\1, '\2')", s, flags=re.I)
        s = re.sub(r'\bDATE\b(?!\s*[\'(\w])', 'CURRENT_DATE', s, flags=re.I) if s.upper() == 'SELECT DATE' else s
        tree = sqlglot.parse_one(s, read='teradata')
        tree = tree.transform(eliminate_qualify)
        types = self.resolve_types(tree)
        for select in tree.find_all(exp.Select):
            grouped = {c.name.lower() for group in select.find_all(exp.Group) for c in group.find_all(exp.Column)}
            if select.args.get('distinct'):
                grouped.update(c.name.lower() for c in select.find_all(exp.Column))
            for column in list(select.find_all(exp.Column)):
                if column.name.lower() in grouped and types.get(column.name.lower(), '').startswith(('character', 'varchar')):
                    replacement = exp.Anonymous(this='RTRIM', expressions=[exp.Cast(this=column.copy(), to=exp.DataType.build('TEXT'))])
                    if column.parent is select:
                        replacement = exp.alias_(replacement, column.name)
                    column.replace(replacement)
        for node in list(tree.walk()):
            if isinstance(node, exp.StrToDate):
                node.set('this', exp.Cast(this=node.this.copy(), to=exp.DataType.build('TEXT')))
                node.set('format', exp.Literal.string(node.args['format'].this.replace('B', ' ')))
            if isinstance(node, exp.Anonymous):
                key = node.name.upper()
                args = node.expressions
                if key in ('ZEROIFNULL', 'NULLIFZERO'):
                    node.replace(exp.Coalesce(this=args[0].copy(), expressions=[exp.Literal.number(0)]) if key == 'ZEROIFNULL' else exp.Nullif(this=args[0].copy(), expression=exp.Literal.number(0)))
                elif key in ('INDEX', 'OREPLACE'):
                    node.set('this', 'STRPOS' if key == 'INDEX' else 'REPLACE')
                elif key == 'TO_CHAR' and len(args) == 2 and isinstance(args[1], exp.Literal):
                    args[1].set('this', args[1].this.replace('B', ' '))
            if isinstance(node, exp.AddMonths):
                node.replace(sqlglot.parse_one(f"({node.this.sql(dialect='postgres')} + ({node.expression.sql(dialect='postgres')}) * INTERVAL '1 month')::date", read='postgres'))
            if isinstance(node, exp.Cast):
                target = node.args['to'].sql().upper()
                value = node.this
                if node.args.get('format'):
                    node.replace(exp.Cast(this=exp.Anonymous(this='TO_CHAR', expressions=[value.copy(), exp.Literal.string(node.args['format'].this.replace('B', ' '))]), to=node.args['to'].copy()))
                elif target in ('INT', 'INTEGER') and isinstance(value, exp.Column):
                    cols = self.resolve_types(tree)
                    if cols.get(value.name.lower()) == 'date':
                        node.replace(exp.Anonymous(this='sfx_td.date_int', expressions=[value.copy()]))
                elif target == 'DATE' and ((isinstance(value, exp.Literal) and not value.is_string) or (isinstance(value, exp.Column) and types.get(value.name.lower()) in ('integer', 'bigint', 'smallint'))):
                    node.replace(exp.Anonymous(this='sfx_td.int_date', expressions=[value.copy()]))
            if isinstance(node, (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE, exp.Between)):
                if isinstance(node.parent, exp.Update):
                    continue
                types = self.resolve_types(tree)
                for key in ('this', 'expression', 'low', 'high'):
                    value = node.args.get(key)
                    if isinstance(value, exp.Column) and types.get(value.name.lower(), '').startswith(('character', 'varchar')):
                        node.set(key, exp.Anonymous(this='RTRIM', expressions=[exp.Cast(this=value.copy(), to=exp.DataType.build('TEXT'))]))
                    elif isinstance(value, exp.Literal) and value.is_string:
                        node.set(key, exp.Literal.string(value.this.rstrip()))
                if isinstance(node.this, exp.Column) and types.get(node.this.name.lower()) == 'date':
                    for key in ('expression', 'low', 'high'):
                        v = node.args.get(key)
                        if isinstance(v, exp.Literal) and not v.is_string:
                            node.set(key, exp.Anonymous(this='sfx_td.int_date', expressions=[v.copy()]))
                elif isinstance(node.expression, exp.Column) and types.get(node.expression.name.lower()) == 'date' and isinstance(node.this, exp.Literal) and not node.this.is_string:
                    node.set('this', exp.Anonymous(this='sfx_td.int_date', expressions=[node.this.copy()]))
            if isinstance(node, exp.Like):
                if self.case_insensitive(tree, node.this):
                    node.replace(exp.ILike(this=exp.Collate(this=node.this.copy(), expression=exp.Identifier(this='C', quoted=True)), expression=node.expression.copy()))
        if isinstance(tree, exp.Insert):
            table = tree.this.this if isinstance(tree.this, exp.Schema) else tree.this
            name = table.sql(dialect='postgres').lower()
            columns = self.columns(name)
            if isinstance(tree.this, exp.Schema):
                lookup = dict(columns)
                columns = [(c.name, lookup[c.name.lower()]) for c in tree.this.expressions]
            query = tree.expression
            def cast_values(values):
                if len(values) != len(columns):
                    return values
                return [exp.Cast(this=v.copy(), to=exp.DataType.build(t, dialect='postgres')) if t.startswith(('character', 'varchar')) else v for v, (_, t) in zip(values, columns)]
            if isinstance(query, exp.Values):
                for row in query.expressions:
                    row.set('expressions', cast_values(row.expressions))
            result = tree.sql(dialect='postgres')
            if isinstance(query, (exp.Select, exp.Union)):
                aliases = [f'c{i}' for i in range(len(columns))]
                expressions = [f'CAST(_td.{a} AS {t})' if t.startswith(('character', 'varchar')) else f'_td.{a}' for a, (_, t) in zip(aliases, columns)]
                result = f'INSERT INTO {tree.this.sql(dialect="postgres")} SELECT {", ".join(expressions)} FROM ({query.sql(dialect="postgres")}) AS _td({", ".join(aliases)})'
            is_set = self.conn.execute('SELECT is_set FROM sfx_td.tables WHERE name=%s', (self.canonical_name(name),)).fetchone()
            if is_set and is_set[0]:
                constraint = self.conn.execute("SELECT conname FROM pg_constraint WHERE conrelid=to_regclass(%s) AND conname LIKE 'td_set_%%'", (name,)).fetchone()[0]
                result += ' ON CONFLICT ON CONSTRAINT ' + constraint + ' DO NOTHING'
            return result, None
        if isinstance(tree, exp.Update):
            types = dict(self.columns(tree.this.sql(dialect='postgres')))
            for assignment in tree.expressions:
                t = types.get(assignment.this.name.lower(), '')
                if t.startswith(('character', 'varchar')):
                    assignment.set('expression', exp.Cast(this=assignment.expression.copy(), to=exp.DataType.build(t, dialect='postgres')))
        return tree.sql(dialect='postgres'), None

    def resolve_types(self, tree):
        result = {}
        for table in tree.find_all(exp.Table):
            relation = table.copy()
            relation.set('alias', None)
            result.update(self.columns(relation.sql(dialect='postgres')))
        return result

    def case_insensitive(self, tree, column):
        if not isinstance(column, exp.Column):
            return False
        for table in tree.find_all(exp.Table):
            if column.table and column.table.lower() != table.alias_or_name.lower():
                continue
            relation = table.copy()
            relation.set('alias', None)
            row = self.conn.execute('SELECT attcollation FROM pg_attribute WHERE attrelid=to_regclass(%s) AND attname=%s', (relation.sql(dialect='postgres'), column.name.lower())).fetchone()
            if row and row[0] == self.conn.execute("SELECT 'sfx_td.ci'::regcollation::oid").fetchone()[0]:
                return True
        return False

    def set_constraint(self, name):
        return 'td_set_' + hashlib.sha256(name.encode()).hexdigest()[:16]

    def canonical_name(self, name):
        row = self.conn.execute("SELECT n.nspname||'.'||c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.oid=to_regclass(%s)", (name,)).fetchone()
        return row[0] if row else name

    def create_table(self, s):
        m = re.match(r'CREATE\s+((?:(?:SET|MULTISET|VOLATILE)\s+)*)TABLE\s+([\w.]+)', s, re.I)
        flags, name = m[1].upper(), m[2].lower()
        start = s.index('(', m.end())
        depth, quote, end = 0, False, start
        for end in range(start, len(s)):
            if s[end] == "'":
                quote = not quote
            if not quote:
                depth += (s[end] == '(') - (s[end] == ')')
                if depth == 0:
                    break
        columns, names, formats = [], [], {}
        for definition in split(s[start + 1:end], ','):
            col = definition.split()[0]
            names.append(col)
            fmt = re.search(r"FORMAT\s+'([^']+)'", definition, re.I)
            if fmt:
                formats[col.lower()] = fmt[1]
            ci = not re.search(r'(?<!NOT )\bCASESPECIFIC\b', definition, re.I)
            definition = re.sub(r"\b(?:FORMAT|TITLE)\s+'[^']*'|\bCHARACTER\s+SET\s+\w+|\b(?:NOT\s+)?CASESPECIFIC\b|\bCOMPRESS(?:\s*\([^)]*\)|\s+'[^']*'|\s+-?\d+(?:\.\d+)?)?", '', definition, flags=re.I)
            if ci and re.search(r'\b(?:VAR)?CHAR\s*\(', definition, re.I):
                definition = re.sub(r'((?:VAR)?CHAR\s*\(\d+\))', r'\1 COLLATE sfx_td.ci', definition, flags=re.I)
            columns.append(definition.strip())
        upi = re.search(r'UNIQUE\s+PRIMARY\s+INDEX(?:\s+\w+)?\s*\(([^)]+)\)', s[end + 1:], re.I)
        if upi:
            columns.append('UNIQUE (' + upi[1] + ')')
        is_set = 'SET' in flags and 'MULTISET' not in flags
        if is_set:
            columns.append(f'CONSTRAINT {self.set_constraint(name)} UNIQUE NULLS NOT DISTINCT ({", ".join(names)})')
        result = 'CREATE ' + ('TEMP ' if 'VOLATILE' in flags else '') + f'TABLE {name} ({", ".join(columns)})'
        def after():
            self.conn.execute('INSERT INTO sfx_td.tables VALUES (%s,%s,%s) ON CONFLICT(name) DO UPDATE SET is_set=excluded.is_set,formats=excluded.formats', (self.canonical_name(name), is_set, json.dumps(formats)))
        return result, after

    def routine(self, s):
        m = re.match(r'(?:CREATE|REPLACE)\s+(MACRO|PROCEDURE)\s+([\w.]+)\s*\(', s, re.I)
        if m:
            start, depth = m.end(), 1
            end = start
            while depth:
                depth += (s[end] == '(') - (s[end] == ')')
                end += 1
            body = s[end:].strip()
            body = re.sub(r'^AS\s*', '', body, flags=re.I)
            if m[1].upper() == 'MACRO':
                body = body.strip()[1:-1]
            else:
                body = re.sub(r'^BEGIN\b|END\s*$', '', body, flags=re.I).strip()
            self.conn.execute('INSERT INTO sfx_td.routines VALUES (%s,%s,%s,%s) ON CONFLICT(name) DO UPDATE SET kind=excluded.kind,params=excluded.params,body=excluded.body', (self.routine_name(m[2]), m[1].upper(), s[start:end - 1], body))
            return True
        m = re.match(r'(EXEC(?:UTE)?|CALL)\s+([\w.]+)\s*\((.*)\)$', s, re.I | re.S)
        if not m:
            return False
        row = self.conn.execute('SELECT kind,params,body FROM sfx_td.routines WHERE name=%s', (self.routine_name(m[2]),)).fetchone()
        if row is None:
            raise psycopg.errors.UndefinedTable('Routine does not exist')
        kind, params, body = row
        params = [p.split() for p in split(params, ',')]
        args = split(m[3], ',')
        values = {}
        for p, arg in zip(params, args):
            name = p[1] if p[0].upper() in ('IN', 'OUT', 'INOUT') else p[0]
            if arg == '?':
                values[name.lower()] = None
            else:
                statement, _ = self.translate('SELECT ' + arg)
                values[name.lower()] = self.conn.execute(statement).fetchone()[0]
        if kind == 'MACRO':
            for statement in split(body):
                self.execute(re.sub(r':(\w+)', lambda n: literal(values[n[1].lower()]), statement))
                if self.errorcode:
                    break
        else:
            from .spl import interpret
            interpret(self, body, values)
            for p in params:
                if p[0].upper() in ('OUT', 'INOUT'):
                    self.say(p[1] + ' = ' + str(values.get(p[1].lower())))
        return True

    def routine_name(self, name):
        return name.lower() if '.' in name else self.conn.execute('SELECT current_schema()').fetchone()[0] + '.' + name.lower()
