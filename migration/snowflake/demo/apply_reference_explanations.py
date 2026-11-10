"""Write the reference explanations for log_run and purge_expired into gate/out/ledger.md."""

import re
from pathlib import Path

LEDGER = Path(__file__).resolve().parents[1] / "gate" / "out" / "ledger.md"
EXPLANATIONS = {
    "log_run": (
        "usp_log_run appends a row every time a package or procedure runs, so the legacy log holds "
        "one row per replay and one per SSIS package. Snowflake keeps the latest dbt run per model "
        "and date in OPS.LOG_RUN, and the SSIS packages are retired (RAW loads are logged under "
        "UBW_LOAD_RAW). Every differing key is a duplicate legacy row or a package row; no procedure "
        "shows a different status or row count."
    ),
    "purge_expired": (
        "The legacy unit is keyed on object_name across the whole append-only run log, so every "
        "object appears once per historical run. usp_purge_expired never ran in the replay window. "
        "Snowflake drops a run's objects by token at teardown, so no purge job is migrated; "
        "OPS.PURGE_EXPIRED shows the latest status per model. Accepted as retired."
    ),
}

text = LEDGER.read_text(encoding="utf-8")
for unit, explanation in EXPLANATIONS.items():
    text = re.sub(
        rf"(### {unit}\n.*?Explanation:)[^\n]*",
        lambda match: f"{match.group(1)} {explanation}",
        text,
        count=1,
        flags=re.S,
    )
LEDGER.write_text(text, encoding="utf-8")
print(f"Explanations written for {', '.join(EXPLANATIONS)} in {LEDGER}")
