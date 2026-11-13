import configparser
import os

import oracledb


def connect():
    config = configparser.ConfigParser()
    config.read(os.environ.get("ETL_CONFIG", "/opt/etl/config.ini"))
    return oracledb.connect(
        user=config.get("insurance", "user"),
        password=config.get("insurance", "password"),
        dsn=config.get("insurance", "dsn"),
    )


def prepare(cursor, ddl):
    try:
        cursor.execute(ddl)
    except oracledb.DatabaseError as exc:
        if exc.args[0].code != 955:
            raise
