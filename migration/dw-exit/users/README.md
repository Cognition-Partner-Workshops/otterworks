# users subject area

One directory per object group; each group is proven on its own:

```sh
make sfx-manifest-board RUN_TOKEN=sfx-sfg1120 BOARD_ROWS=200 PARITY_TARGET=duckdb \
  GROUP=migration/dw-exit/users/<group> SFX_SNOWFLAKE_REASON='<why the Snowflake column is red>'
```

A group directory holds:

- `group.yaml`: the manifest object ids in the group, and optional `outputs` (object id to
  `SFX_<AREA>.<RELATION>` list) for objects whose manifest entry declares no output relation.
- `10_load.sql`, `30_views.sql`: Snowflake conversions, run in DuckDB against the group's
  `STG_` landing tables.
- `hook.py` (optional): `materialize(before, after, ready, errors)` for outputs SQL can't build.
- `board.json`: the group's parity rows (row count, column profile, keyed row hash, sampled
  differences) and a `snowflake` column per row.
