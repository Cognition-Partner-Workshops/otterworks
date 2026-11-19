"""Spark-feed documents outputs, independent of warehouse snapshots."""

import argparse
import csv
import difflib
import hashlib
import json
import os
import re
import uuid
from pathlib import Path

from pyspark.sql import functions as F
from pyspark.sql.types import StringType
from pyspark.sql.types import DoubleType, LongType, StructField, StructType
from pyspark.sql.window import Window

from .documents_binary import extract_document
from .ingest import business_date
from .layout import data_root, delta_path
from .session import create_session


SCHEMAS = {
    'DOCUMENT': ('documents', 'DOCUMENT_ID long, OWNER_USER_ID long, FOLDER_ID long, TITLE string, CREATED_AT timestamp, STATUS string'),
    'FILE_OBJECT': ('documents', 'FILE_OBJECT_ID long, DOCUMENT_ID long, SIZE_BYTES long, CHECKSUM string, STORAGE_KEY string'),
    'APP_USER': ('users', 'USER_ID long, EMAIL string, DISPLAY_NAME string, CREATED_AT timestamp, STATUS string'),
    'FOLDER': ('documents', 'FOLDER_ID long, OWNER_USER_ID long, PARENT_FOLDER_ID long, FOLDER_NAME string'),
    'DOC_SHARE': ('documents', 'DOC_SHARE_ID long, DOCUMENT_ID long, OWNER_USER_ID long, SHARED_WITH_USER_ID long, PERMISSION string'),
    'DOC_TAG': ('documents', 'DOC_TAG_ID long, DOCUMENT_ID long, TAG string'),
    'SEARCH_INDEX_LOG': ('documents', 'SEARCH_INDEX_LOG_ID long, DOCUMENT_ID long, EVENT_AT timestamp, RAW_LINE string, STATUS string'),
}
INPUTS = {
    'docs_storage_by_owner': ['DOCUMENT', 'FILE_OBJECT', 'APP_USER'],
    'docs_share_activity': ['DOC_SHARE', 'DOCUMENT'],
    'docs_folder_legacy_report': ['FOLDER', 'DOCUMENT'],
    'docs_search_log_parse': ['SEARCH_INDEX_LOG'],
    'docs_tag_normalize': ['DOC_TAG'],
    'docs_event_export_hourly': ['DOCUMENT'],
    'lake_compaction_documents': [],
}
SECOND_SCHEMAS = {
    'DOC_VERSION': ('documents', 'DOC_VERSION_ID long, DOCUMENT_ID long, VERSION_NUMBER long, BODY string, CREATED_AT timestamp'),
    'COLLAB_SESSION': ('documents', 'COLLAB_SESSION_ID long, DOCUMENT_ID long, USER_ID long, SESSION_ID string, EVENT_AT timestamp'),
}
SECOND_INPUTS = {
    'docs_folder_tree_walk': ['FOLDER'],
    'doc_share_graph_reach': ['DOC_SHARE'],
    'collab_session_sessionize': ['COLLAB_SESSION'],
    'doc_version_diff_stats': ['DOC_VERSION'],
    'file_object_binary_extract': ['FILE_OBJECT', 'FILE_OBJECT_BLOBS'],
}
INPUTS.update(SECOND_INPUTS)
EXTRACT_SCHEMA = StructType([StructField('MEDIA_TYPE', StringType()), StructField('TEXT', StringType()),
                             StructField('PAGE_COUNT', LongType()), StructField('SHA256', StringType()),
                             StructField('ERROR', StringType())])


def walk_folder(folder, parents):
    current, depth = folder, 0
    for _ in range(20):
        parent = parents.get(current)
        current, depth = parent or current, depth + int(parent is not None)
    return folder, current, depth


def sessionize(group):
    (user, document), times = group
    ordered = sorted(times)
    if not ordered:
        return []
    start = previous = ordered[0]
    number, result = 1, []
    for timestamp in ordered[1:]:
        if (timestamp - previous).total_seconds() > 1800:
            result.append((user, document, number, start, previous))
            number, start = number + 1, timestamp
        previous = timestamp
    return result + [(user, document, number, start, previous)]


def similarity(before, after):
    return difflib.SequenceMatcher(None, before or '', after or '').ratio()


def parse_action(value):
    match = re.search(r'action=(\w+)', value or '')
    return match.group(1) if match else None


def normalize_tag(value):
    return re.sub(r'\s+', '-', (value or '').strip().lower())


def verify_inputs(root, tables=None, expected=None):
    manifest = json.loads((root / 'manifest.json').read_text())
    if expected is not None and manifest != expected:
        raise ValueError('Spark manifest changed during execution')
    files = {key: value for key, value in manifest['files'].items()
             if tables is None or key.split('/')[1] in tables}
    actual = {str(path.relative_to(root)) for path in root.glob('*/*/*')
              if path.is_file() and (tables is None or path.parent.name in tables)}
    if actual != set(files) or tables is not None and {key.split('/')[1] for key in files} != set(tables):
        raise ValueError('Spark manifest does not describe the requested input files')
    for relative, digest in files.items():
        path = root / relative
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Spark input changed: ' + relative)
    return manifest


def read_input(spark, root, table, infer=False):
    if table == 'FILE_OBJECT_BLOBS':
        return spark.read.format('binaryFile').load(str(root / 'documents/FILE_OBJECT_BLOBS/*'))
    area, schema = {**SCHEMAS, **SECOND_SCHEMAS}[table]
    paths = sorted((root / area / table).glob('*.psv'))
    if not paths:
        raise FileNotFoundError(f'Spark feed missing: {area}/{table}')
    expected = [column.split()[0] for column in schema.split(', ')]
    for path in paths:
        with path.open(newline='') as handle:
            if next(csv.reader(handle, delimiter='|'), None) != expected:
                raise ValueError('Spark header differs: ' + str(path))
    reader = spark.read.option('header', True).option('sep', '|').option('escape', '"')
    reader = reader.option('inferSchema', True) if infer else reader.schema(schema)
    return reader.csv([str(path) for path in paths])


def transform(spark, job, frames, exported=None):
    if job == 'docs_folder_tree_walk':
        folders = frames['FOLDER'].select('FOLDER_ID', 'PARENT_FOLDER_ID').rdd
        parents = spark.sparkContext.broadcast(dict(folders.map(tuple).collect()))
        return spark.createDataFrame(folders.map(lambda row: walk_folder(row.FOLDER_ID, parents.value)),
                                     'FOLDER_ID long, ROOT_FOLDER_ID long, DEPTH long')
    if job == 'doc_share_graph_reach':
        edges = frames['DOC_SHARE'].select('OWNER_USER_ID', 'SHARED_WITH_USER_ID').rdd.map(tuple).cache()
        visited = frontier = spark.sparkContext.parallelize([(1, 0)], 2)
        for depth in range(1, 5):
            frontier = frontier.join(edges).map(lambda row: (row[1][1], depth)).subtractByKey(visited).cache()
            visited = visited.union(frontier).reduceByKey(min)
        return spark.createDataFrame(visited, 'USER_ID long, DISTANCE long')
    if job == 'collab_session_sessionize':
        events = frames['COLLAB_SESSION'].rdd.map(lambda row: ((row.USER_ID, row.DOCUMENT_ID), row.EVENT_AT))
        return spark.createDataFrame(events.groupByKey().flatMap(sessionize),
                                     'USER_ID long, DOCUMENT_ID long, SESSION_NUMBER long, START_AT timestamp, END_AT timestamp')
    if job == 'doc_version_diff_stats':
        previous = F.lag('BODY').over(Window.partitionBy('DOCUMENT_ID').orderBy('VERSION_NUMBER'))
        return frames['DOC_VERSION'].withColumn('PREVIOUS_BODY', previous).withColumn(
            'SIMILARITY', F.udf(similarity, DoubleType())('PREVIOUS_BODY', 'BODY'))
    if job == 'file_object_binary_extract':
        extracted = frames['FILE_OBJECT_BLOBS'].select(
            F.regexp_extract('path', r'(documents/FILE_OBJECT_BLOBS/[^/]+)$', 1).alias('STORAGE_KEY'),
            F.udf(extract_document, EXTRACT_SCHEMA)('content').alias('EXTRACT')).select('STORAGE_KEY', 'EXTRACT.*')
        return frames['FILE_OBJECT'].join(extracted, 'STORAGE_KEY')
    if job == 'docs_storage_by_owner':
        joined = (frames['DOCUMENT'].alias('d').join(frames['FILE_OBJECT'].alias('f'), 'DOCUMENT_ID')
                  .join(frames['APP_USER'].alias('u'), F.col('d.OWNER_USER_ID') == F.col('u.USER_ID')))
        return joined.groupBy('u.USER_ID', 'u.EMAIL').agg(F.count('*').alias('FILE_COUNT'),
                                                         F.sum('f.SIZE_BYTES').alias('SIZE_BYTES'))
    if job == 'docs_share_activity':
        joined = frames['DOC_SHARE'].alias('s').join(frames['DOCUMENT'].alias('d'), 'DOCUMENT_ID')
        return joined.groupBy('d.OWNER_USER_ID', 's.PERMISSION').agg(
            F.count('*').alias('SHARES'), F.countDistinct('s.SHARED_WITH_USER_ID').alias('RECIPIENTS'))
    if job == 'docs_folder_legacy_report':
        joined = frames['FOLDER'].alias('f').join(frames['DOCUMENT'].alias('d'), 'FOLDER_ID', 'left')
        return joined.groupBy('FOLDER_ID', 'f.FOLDER_NAME', 'f.PARENT_FOLDER_ID').agg(
            F.count('d.DOCUMENT_ID').alias('DOCUMENTS'))
    if job == 'docs_search_log_parse':
        return frames['SEARCH_INDEX_LOG'].withColumn('PARSED_ACTION', F.udf(parse_action, StringType())('RAW_LINE'))
    if job == 'docs_tag_normalize':
        return frames['DOC_TAG'].withColumn('NORMALIZED_TAG', F.udf(normalize_tag, StringType())('TAG'))
    if job == 'docs_event_export_hourly':
        return frames['DOCUMENT'].withColumn('EXPORT_BUCKET', F.pmod(F.col('DOCUMENT_ID'), F.lit(10000)).cast('int'))
    if job == 'lake_compaction_documents':
        if exported is None:
            raise ValueError('Compaction requires an exported snapshot')
        return exported.coalesce(4)
    raise ValueError('Unknown documents Spark job: ' + job)


def publish(frame, output, partitioned=False, validate=None):
    output.parent.mkdir(parents=True, exist_ok=True)
    version = output.parent / '.versions' / output.name / uuid.uuid4().hex
    writer = (frame.repartition(8, 'EXPORT_BUCKET').write.partitionBy('EXPORT_BUCKET')
              if partitioned else frame.write)
    writer.mode('error').parquet(str(version))
    if not (version / '_SUCCESS').is_file():
        raise RuntimeError('Spark publication has no success marker')
    if validate is not None:
        validate()
    pointer = output.with_name('.' + output.name + '-' + uuid.uuid4().hex)
    pointer.symlink_to(version.relative_to(output.parent), target_is_directory=True)
    os.replace(pointer, output)
    return version


def output_root(day):
    business_date(day)
    return data_root() / 'exports/documents/spark' / day


def run(spark, landing, day, jobs):
    business_date(day)
    root = Path(landing) / 'spark' / day
    for job in jobs:
        if job not in INPUTS:
            raise ValueError('Unknown documents Spark job: ' + job)
        tables = INPUTS[job]
        manifest = None
        if tables:
            manifest = verify_inputs(root, tables)
        frames = {table: read_input(spark, root, table, infer=job == 'docs_share_activity')
                  for table in INPUTS[job]}
        exported = None
        exported_version = None
        if job == 'lake_compaction_documents':
            exported_version = (output_root(day) / 'docs_event_export_hourly').resolve(strict=True)
            exported = spark.read.parquet(str(exported_version))
        result = transform(spark, job, frames, exported)
        validate = (lambda: verify_inputs(root, tables, manifest)) if tables else None
        version = publish(result, output_root(day) / job, job == 'docs_event_export_hourly', validate)
        name = 'spark_runtime_' + job + '_' + day
        snapshot = spark.read.schema(result.schema).parquet(str(version)).withColumn('_business_date', F.lit(day))
        (snapshot.write.format('delta').mode('overwrite').option('overwriteSchema', 'true')
         .option('path', str(delta_path('silver', 'documents', name)))
         .saveAsTable('silver_documents.' + name))
        provenance = dict(job=job, business_date=day, inputs=manifest, output_version=str(version),
                          export_input_version=str(exported_version) if exported_version else None,
                          runtime_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        (output_root(day) / (job + '.provenance.json')).write_text(json.dumps(provenance, indent=2) + '\n')
        print(f'documents.spark.{job}: published {version}', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--landing', type=Path, required=True)
    parser.add_argument('--business-date', required=True)
    parser.add_argument('--jobs', nargs='+', choices=list(INPUTS), required=True)
    args = parser.parse_args()
    spark = create_session()
    try:
        run(spark, args.landing, args.business_date, args.jobs)
    finally:
        spark.stop()


if __name__ == '__main__':
    main()
