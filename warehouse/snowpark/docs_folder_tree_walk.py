"""Replaces the Spark lake output documents/docs_folder_tree_walk."""

import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[2]))
from warehouse.run_config import render as _run_render



def run(session):
    database = session.get_current_database()
    function = f'{database}."MART_SPARK"."DOCS_FOLDER_TREE_WALK_WALK"'
    session.sql(f"""
        create or replace temporary function {function}(folder_id number, parent_folder_id number)
        returns table(FOLDER_ID number, ROOT_FOLDER_ID number, DEPTH number)
        language python
        runtime_version = '3.10'
        handler = 'FolderTreeWalk'
        as $$
class FolderTreeWalk:
    def __init__(self):
        self.rows = []

    def process(self, folder_id, parent_folder_id):
        self.rows.append((folder_id, parent_folder_id))

    def end_partition(self):
        lookup = dict(self.rows)
        for fid, _ in self.rows:
            root, depth = fid, 0
            for _ in range(20):
                nxt = lookup.get(root)
                root, depth = (nxt or root), depth + int(nxt is not None)
            yield fid, root, depth
$$
    """).collect()
    result = session.sql(f"""
        select walk.FOLDER_ID::number(38,0) as FOLDER_ID,
               walk.ROOT_FOLDER_ID::number(38,0) as ROOT_FOLDER_ID,
               walk.DEPTH::number(38,0) as DEPTH
        from {database}."SPARK_RAW_DOCUMENTS"."FOLDER" folders,
             table({function}(folders.FOLDER_ID, folders.PARENT_FOLDER_ID)
                   over (partition by 1)) walk
    """)
    result.write.save_as_table(
        [database, "MART_SPARK", "DOCS_FOLDER_TREE_WALK"],
        mode="overwrite",
        comment=_run_render("__RUN_TOKEN__ Replaces the Spark lake output documents/docs_folder_tree_walk."),
    )
