"""Thin launcher for the plugin's migration-fanout workflow.py under run_workflow.

run_workflow has no env parameter, so this sets the env the plugin script expects
(WAVE_MANIFEST, WAVE_RUN_ID, WAVE_RESUME) and chdirs to the repo, then executes the
plugin script byte-for-byte in this namespace (the runtime shim's agent/pipeline/... stay
visible). Edit only the CONFIG block between runs; commit it with the wave.
"""
import os
import glob

# --- CONFIG (orchestrator edits) ---
REPO = "/home/ubuntu/repos/otterworks"
WAVE = 1
RUN_ID = "wfr-cc00292593f54696bc43d58b68bedd34"
RESUME = True
# -----------------------------------

os.chdir(REPO)
os.environ["WAVE_MANIFEST"] = f"{REPO}/.migration/waves/wave-{WAVE}.json"
if RESUME:
    os.environ["WAVE_RESUME"] = "1"
if not RUN_ID:
    hint = {k: v for k, v in os.environ.items() if "RUN" in k.upper() or "WORKFLOW" in k.upper()}
    raise SystemExit("WAVE_RUN_ID not configured: record this invocation's run_id into RUN_ID and "
                     f"re-run with run_id=<same>. env hints: {sorted(hint)}")
os.environ["WAVE_RUN_ID"] = RUN_ID

_wf = glob.glob("/opt/.devin/plugins/cache/*mongo-migration-plugin*/*/skills/migration-fanout/workflow.py")[0]
exec(compile(open(_wf).read(), _wf, "exec"), globals())
