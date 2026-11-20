"""Execute shipped users SQL locally, extracting SQL from Scripting wrappers."""
import re

import sqlglot
from sqlglot import exp

from warehouse.run_config import render
from .connection import validate_date
from .subjects import SUBJECTS


STAGES = ('10_load.sql', '20_routines.sql', '30_views.sql')


def statements(path, business_date, procedure='P_ACTIVITY_DAILY'):
    business_date = validate_date(business_date)
    text = render(path.read_text()).replace('${BUSINESS_DATE}', business_date)
    if path.name == '20_routines.sql':
        bodies = re.findall(r'CREATE OR REPLACE PROCEDURE\s+\S+\.(\w+)\s*\(.*?\$\$(.*?)\$\$;', text, re.S | re.I)
        monthly = [body for name, body in bodies if name.upper() == procedure]
        if len(monthly) != 1:
            raise ValueError('Expected one '+procedure+' body')
        text = monthly[0].split('BEGIN', 1)[1]
        text = re.sub(r'run_day\s*:=\s*TO_DATE\(p_day,\s*\x27YYYYMMDD\x27\);', '', text, flags=re.I)
        text = re.sub(r'n\s*:=\s*SQLROWCOUNT;', '', text, flags=re.I)
        text = re.sub(r'RETURN n;\s*END;\s*$', '', text, flags=re.I)
        text = text.replace(':run_day', f"TO_DATE('{business_date}', 'YYYYMMDD')")
    parsed = sqlglot.parse(text, read='snowflake')
    for statement in parsed:
        if statement is None:
            continue
        if not isinstance(statement, (exp.Insert, exp.Delete, exp.Update, exp.Merge, exp.Create)):
            raise ValueError(f'Unsupported local users statement: {type(statement).__name__}')
        for table in statement.find_all(exp.Table):
            table.set('catalog', None)
        for node in reversed(list(statement.walk())):
            if isinstance(node, exp.Anonymous) and node.name.upper() == 'TO_DATE':
                value, fmt = node.expressions
                formats = {'YYYYMMDD':'%Y%m%d'}
                if not isinstance(fmt, exp.Literal) or fmt.this not in formats:
                    raise ValueError('Unsupported TO_DATE format')
                node.replace(exp.StrToDate(this=value.copy(), format=exp.Literal.string(formats[fmt.this])))
            elif isinstance(node, exp.ToChar):
                fmt = node.args.get('format')
                formats = {'YYYY-MM':'%Y-%m','YYYYMM':'%Y%m'}
                if not isinstance(fmt, exp.Literal) or fmt.this not in formats:
                    raise ValueError('Unsupported TO_CHAR format')
                node.replace(exp.TimeToStr(this=node.this.copy(), format=exp.Literal.string(formats[fmt.this])))
            elif isinstance(node, exp.ToNumber):
                if node.args.get('format') or node.args.get('precision') or node.args.get('scale'):
                    raise ValueError('Unsupported TO_NUMBER precision or format')
                node.replace(exp.Cast(this=node.this.copy(),to=exp.DataType.build('DECIMAL(38,0)')))
        if isinstance(statement, exp.Create):
            statement.set('properties', None)
        yield statement


def execute(after, conversion_dir, ready, business_date, subject='users'):
    errors = {}
    failed = False
    for filename in SUBJECTS[subject]['stages']:
        path = conversion_dir / filename
        try:
            for statement in statements(path, business_date, SUBJECTS[subject]['procedure']):
                after.execute(statement.sql(dialect='duckdb', comments=False))
                if isinstance(statement, (exp.Create, exp.Insert)):
                    target = statement.this.this if isinstance(statement.this, exp.Schema) else statement.this
                    ready.add(target.sql(dialect='duckdb', comments=False).upper())
        except Exception as error:
            errors['*'] = f'{filename}: {type(error).__name__}: {error}'
            failed = True
            break
    if failed:
        ready.clear()
    return errors
