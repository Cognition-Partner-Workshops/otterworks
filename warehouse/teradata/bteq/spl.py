import re

import sqlglot
from sqlglot import exp

from .runner import literal


def substitute(statement, values):
    invocation = re.match(r'((?:EXEC(?:UTE)?|CALL)\s+[\w.]+)\s*\((.*)\)$', statement, re.I | re.S)
    if invocation:
        arguments = substitute('SELECT ' + invocation[2], values)
        return invocation[1] + '(' + re.sub(r'^SELECT\s+', '', arguments, flags=re.I) + ')'
    tree = sqlglot.parse_one(statement, read='teradata')
    for node in list(tree.find_all(exp.Column)):
        key = (node.table + '.' + node.name if node.table else node.name).lower()
        if key in values:
            node.replace(sqlglot.parse_one(literal(values[key]), read='teradata'))
    return tree.sql(dialect='teradata')


def tokenize(body):
    pattern = r"('(?:''|[^'])*')|\b(END\s+(?:IF|WHILE|FOR)|ELSEIF\b.*?\bTHEN|IF\b.*?\bTHEN|WHILE\b.*?\bDO|FOR\b.*?\bDO|ELSE)\b|\b(CASE|END)\b|;"
    tokens, start, case_depth = [], 0, 0
    for m in re.finditer(pattern, body, re.I | re.S):
        if m[1]:
            continue
        if m[3]:
            case_depth += 1 if m[3].upper() == 'CASE' else -1
            continue
        if case_depth:
            continue
        prefix = body[start:m.start()].strip()
        if prefix:
            tokens.append(prefix)
        if m[2]:
            tokens.append(m[2].strip())
        start = m.end()
    if body[start:].strip():
        tokens.append(body[start:].strip())
    return tokens


def parse(tokens, index=0):
    nodes = []
    while index < len(tokens):
        token = tokens[index]
        upper = token.upper()
        if upper.startswith(('END ', 'ELSE')):
            break
        index += 1
        if upper.startswith(('IF ', 'WHILE ', 'FOR ')):
            children, index = parse(tokens, index)
            branches = [(token, children)]
            while index < len(tokens) and tokens[index].upper().startswith(('ELSEIF ', 'ELSE')):
                header = tokens[index]
                children, index = parse(tokens, index + 1)
                branches.append((header, children))
            if index >= len(tokens) or not tokens[index].upper().startswith('END '):
                raise ValueError('Unclosed SPL block')
            index += 1
            nodes.append(('block', branches))
        else:
            nodes.append(('sql', token))
    return nodes, index


def interpret(runner, body, values):
    nodes, _ = parse(tokenize(body))

    def refresh():
        values.update(activity_count=runner.activitycount, sqlcode=runner.errorcode, sqlstate=runner.sqlstate)

    def evaluate(expression):
        refresh()
        statement, _ = runner.translate(substitute('SELECT ' + expression, values))
        return runner.conn.execute(statement).fetchone()[0]

    def condition(header):
        return bool(evaluate(re.sub(r'^(?:IF|ELSEIF|WHILE)\s+|\s+(?:THEN|DO)$', '', header, flags=re.I)))

    def execute(items):
        for kind, node in items:
            if kind == 'block':
                header, children = node[0]
                if header.upper().startswith('WHILE'):
                    count = 0
                    while condition(header):
                        execute(children)
                        count += 1
                        if count > 100000:
                            raise ValueError('SPL iteration limit exceeded')
                elif header.upper().startswith('FOR'):
                    m = re.match(r'FOR\s+(\w+)\s+AS\s+(?:\w+\s+CURSOR\s+FOR\s+)?(SELECT.*?)\s+DO$', header, re.I | re.S)
                    runner.execute(substitute(m[2], values))
                    rows, columns = runner.rows[:], runner.headers[:]
                    for row in rows:
                        values.update({m[1].lower() + '.' + c.lower(): v for c, v in zip(columns, row)})
                        execute(children)
                else:
                    for h, children in node:
                        if h.upper() == 'ELSE' or condition(h):
                            execute(children)
                            break
            elif node.upper().startswith('DECLARE '):
                m = re.match(r'DECLARE\s+(\w+)\s+.+?(?:\s+DEFAULT\s+(.*))?$', node, re.I | re.S)
                values[m[1].lower()] = evaluate(m[2]) if m[2] else None
            elif node.upper().startswith('SET '):
                m = re.match(r'SET\s+(\w+)\s*=\s*(.*)', node, re.I | re.S)
                values[m[1].lower()] = evaluate(m[2])
            else:
                refresh()
                m = re.match(r'SELECT\s+(.*?)\s+INTO\s+(:?\w+(?:\s*,\s*:?\w+)*)(\s+FROM\b.*)?$', node, re.I | re.S)
                if m:
                    runner.execute(substitute('SELECT ' + m[1] + (m[3] or ''), values))
                    if runner.rows:
                        values.update({k.strip().lstrip(':').lower(): v for k, v in zip(m[2].split(','), runner.rows[0])})
                else:
                    runner.execute(substitute(node, values))
    execute(nodes)
