import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db2_host: str
    db2_port: int
    db2_database: str
    db2_user: str
    db2_password: str
    oracle_dsn: str
    oracle_user: str
    oracle_password: str
    postgres: dict
    mongo: dict
    mongo_database: str

    @classmethod
    def environment(cls):
        e = os.environ
        return cls(e['DB2_HOST'], int(e['DB2_PORT']), e['DB2_DATABASE'], e['DB2_USER'],
                   e['DB2_PASSWORD'], e['ORACLE_DSN'], e['ORACLE_USER'], e['ORACLE_PASSWORD'],
                   dict(host=e['PGHOST'], port=int(e['PGPORT']), dbname=e['PGDATABASE'],
                        user=e['PGUSER'], password=e['PGPASSWORD'], connect_timeout=20),
                   dict(host=e['MONGO_HOST'], port=int(e['MONGO_PORT']), username=e['MONGO_USER'],
                        password=e['MONGO_PASSWORD'], authSource=e['MONGO_AUTH_SOURCE'],
                        serverSelectionTimeoutMS=20000), e['MONGO_DATABASE'])
