from datetime import datetime, timezone
import os
from pathlib import Path
import shutil

from common.runtime import landing, save_partition, session

MAX_DEPTH = 20


def walk(lookup, folder_id):
    """Follow parent pointers up to MAX_DEPTH hops, matching the legacy 20-pass RDD loop."""
    root, depth = folder_id, 0
    for _ in range(MAX_DEPTH):
        parent = lookup.get(root)
        if parent is None:
            break
        root, depth = parent, depth + 1
    return folder_id, root, depth


def drop_unpartitioned(path):
    """Legacy runs wrote parquet straight into the job directory; keep only run_date= partitions."""
    root = Path(path)
    if not root.is_dir():
        return
    for entry in root.iterdir():
        if entry.name.startswith("run_date="):
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def main():
    spark = session("docs_folder_tree_walk")
    run_date = os.environ.get("SFX_RUN_DATE") or datetime.now(timezone.utc).date().isoformat()
    folders = landing(spark, "FOLDER").select("FOLDER_ID", "PARENT_FOLDER_ID")
    # Parent pointers are small enough to collect once; the walk then runs in a single map stage.
    lookup = spark.sparkContext.broadcast(
        {row.FOLDER_ID: row.PARENT_FOLDER_ID for row in folders.collect() if row.PARENT_FOLDER_ID is not None}
    )
    paths = folders.rdd.map(lambda row: walk(lookup.value, row.FOLDER_ID))
    result = spark.createDataFrame(paths, "FOLDER_ID long, ROOT_FOLDER_ID long, DEPTH long")
    drop_unpartitioned(f"{os.environ.get('LAKE_DIR', '/opt/lake')}/documents/docs_folder_tree_walk")
    save_partition(result, "documents", "docs_folder_tree_walk", run_date)
    spark.stop()


if __name__ == "__main__":
    main()
