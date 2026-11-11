"""Print tagged statement history without SQL text or credentials."""
from load_control import connect, execute

QUERY = """SELECT statement_id, execution_status,
  regexp_extract(statement_text, 'step=([^ *]+)', 1) AS step,
  statement_type
FROM system.query.history
WHERE statement_text LIKE '/* run=dbx-d1111 act=assess%'
ORDER BY start_time, statement_id"""


if __name__ == '__main__':
    print('/* run=dbx-d1111 act=assess step=history */ ' + QUERY)
    with connect() as connection, connection.cursor() as cursor:
        for row in execute(cursor, 'history', QUERY).fetchall():
            print(tuple(row))
