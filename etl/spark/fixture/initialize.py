import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.request import urlretrieve
from zipfile import ZipFile, ZIP_DEFLATED

from generate_fixture import generate

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "jobs/py"))
from common.schemas import SCHEMAS, TABLES


def load_sql(landing):
    statements = ["BEGIN;"]
    for area, tables in TABLES.items():
        schema = "sfx_" + area
        statements.append(f"CREATE SCHEMA IF NOT EXISTS {schema};")
        for table in tables:
            columns = ", ".join(f"{name} {kind}" for name, kind in SCHEMAS[table])
            statements.extend((f"DROP TABLE IF EXISTS {schema}.{table};",
                               f"CREATE TABLE {schema}.{table} ({columns});"))
            files = sorted((landing / area / table).glob("*.psv"))
            if not files:
                raise ValueError(f"No landing files for {area}/{table}")
            for file in files:
                path = f"/opt/landing/{area}/{table}/{file.name}"
                statements.append(f"COPY {schema}.{table} FROM '{path}' WITH "
                                  "(FORMAT csv, HEADER true, DELIMITER '|', NULL '');")
    return "\n".join([*statements, "COMMIT;", ""])


def main():
    data = Path("/opt/runtime")
    cache = ROOT / ".cache"
    landing = Path("/opt/landing")
    for directory in (data / "lake", data / "eventlogs", cache / "jars", cache / "classes"):
        directory.mkdir(parents=True, exist_ok=True)
    generate(landing, int(os.environ.get("ROWS_PER_TABLE", "200000")), 1110)
    (data / "load.sql").write_text(load_sql(landing))
    for path in (ROOT / "history/eventlogs").glob("*.zstd"):
        shutil.copy2(path, data / "eventlogs" / path.name)
    base = "https://maven-central.storage-download.googleapis.com/maven2"
    for artifact in ("org/postgresql/postgresql/42.7.4/postgresql-42.7.4.jar",
                     "org/scala-lang/scala-compiler/2.12.18/scala-compiler-2.12.18.jar"):
        target = cache / "jars" / artifact.split("/")[-1]
        if not target.is_file():
            temporary = target.with_suffix(".tmp")
            urlretrieve(f"{base}/{artifact}", temporary)
            temporary.replace(target)
    with ZipFile(cache / "common.zip", "w", ZIP_DEFLATED) as archive:
        for path in sorted((ROOT / "jobs/py/common").glob("*.py")):
            if path.name != "package.py":
                archive.write(path, "common/" + path.name)
    sources = sorted((ROOT / "scala/src/main/scala").rglob("*.scala"))
    subprocess.run(["java", "-cp", f"{cache}/jars/scala-compiler-2.12.18.jar:/opt/spark/jars/*",
                    "scala.tools.nsc.Main", "-classpath", "/opt/spark/jars/*", "-d",
                    str(cache / "classes"), *map(str, sources)], check=True)
    subprocess.run(["jar", "cf", str(cache / "sfx-spark-jobs.jar"), "-C",
                    str(cache / "classes"), "."], check=True)
    for directory in (data, landing, cache):
        for path in [directory, *directory.rglob("*")]:
            os.chown(path, 185, 185)
    data.chmod(0o777)
    cache.chmod(0o777)
    (cache / "common.zip").chmod(0o666)


if __name__ == "__main__":
    main()
