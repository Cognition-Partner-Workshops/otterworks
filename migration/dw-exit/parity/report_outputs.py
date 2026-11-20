"""Translate legacy audit resultset queries for the local PostgreSQL emulator."""
import sqlglot
from sqlglot import exp


def postgres_query(query):
    parsed = sqlglot.parse_one(query, read='teradata')
    for node in list(parsed.find_all(exp.Anonymous)):
        if node.name.upper() == 'ZEROIFNULL':
            node.replace(exp.Coalesce(this=node.expressions[0].copy(), expressions=[exp.Literal.number(0)]))
    return parsed.sql(dialect='postgres')
