from datetime import datetime, timezone
from functools import reduce
import heapq
import math
import os

from pyspark.sql import DataFrame
from pyspark.sql.functions import broadcast, col, regexp_extract, udf
from pyspark.sql.types import LongType, StringType, StructField, StructType
from common.binary_documents import extract_document
from common.runtime import landing, save_partition, session


EXTRACT_SCHEMA = StructType([
    StructField("MEDIA_TYPE", StringType()), StructField("TEXT", StringType()),
    StructField("PAGE_COUNT", LongType()), StructField("SHA256", StringType()),
    StructField("ERROR", StringType()),
])
TARGET_GROUP_BYTES = 64 * 1024 * 1024

extract = udf(extract_document, EXTRACT_SCHEMA)


def balanced_groups(files, groups):
    """Largest file first into the lightest group, so every task gets the same bytes and media mix."""
    heap = [(0, index, []) for index in range(groups)]
    for path, length in sorted(files, key=lambda item: (-item[1], item[0])):
        size, index, paths = heapq.heappop(heap)
        paths.append(path)
        heapq.heappush(heap, (size + length, index, paths))
    return [paths for _, _, paths in sorted(heap, key=lambda item: item[1]) if paths]


def group_count(spark, files, total_bytes):
    cores = int(spark.conf.get("spark.cores.max", str(spark.sparkContext.defaultParallelism)))
    return min(len(files), max(cores, math.ceil(total_bytes / TARGET_GROUP_BYTES)))


def main():
    spark = session("file_object_binary_extract")
    run_date = os.environ.get("SFX_RUN_DATE") or datetime.now(timezone.utc).date().isoformat()
    blobs = f"{os.environ.get('LANDING_DIR', '/opt/landing')}/documents/FILE_OBJECT_BLOBS"
    listing = [(row.path, row.length) for row in
               spark.read.format("binaryFile").load(blobs).select("path", "length").collect()]
    total_bytes = sum(length for _, length in listing)
    print(f"BINARY_INPUT_FILES={len(listing)} BINARY_INPUT_BYTES={total_bytes}")
    # Explicit file lists are stat'ed on the driver instead of launching a listing job per group.
    spark.conf.set("spark.sql.sources.parallelPartitionDiscovery.threshold", str(len(listing) + 1))
    groups = balanced_groups(listing, group_count(spark, listing, total_bytes)) if listing else []
    # One partition per balanced group: coalesce(1) merges a group's splits without a shuffle.
    reads = [spark.read.format("binaryFile").load(paths).coalesce(1) for paths in groups]
    files = reduce(DataFrame.unionByName, reads) if reads else spark.read.format("binaryFile").load(blobs)
    extracted = files.select(
        regexp_extract("path", r"(documents/FILE_OBJECT_BLOBS/[^/]+)$", 1).alias("STORAGE_KEY"),
        extract(col("content")).alias("EXTRACT"),
    ).select("STORAGE_KEY", "EXTRACT.*").cache()
    print(f"BINARY_GROUPS={len(groups)} BINARY_EXTRACTED={extracted.count()}")
    result = landing(spark, "FILE_OBJECT").join(broadcast(extracted), "STORAGE_KEY")
    save_partition(result, "documents", "file_object_binary_extract", run_date)
    print(f"BINARY_OUTPUT_ROWS={result.count()} RUN_DATE={run_date}")
    spark.stop()


if __name__ == "__main__":
    main()
