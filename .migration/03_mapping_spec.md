# 03 — Mapping Specification

Version: **v0 (empty)**. Owned by `!mongo_inventory_and_model` (phase 2); populated after
STOP A, frozen at STOP B; append-only afterwards via the decision log (05).

Machine-readable twin: `03_mapping_spec.json` (produced in phase 2). Every embed declares
element key + graded fields; every batch scope is a `${param}` placeholder, never a literal.
