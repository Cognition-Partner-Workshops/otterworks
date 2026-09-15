"""Read the deployed pipeline-3 jobs back from the Jobs API and assert the orchestration rules.

Evidence for the wave-3 orchestration unit, which moves no data and so has no recon run.
The rules are the ones pipeline 2 paid for:

  * every schedule PAUSED, so deploying can never start anything on a timer;
  * max_concurrent_runs 1 with queueing, so a late run waits instead of racing;
  * no cluster definitions anywhere - serverless only;
  * retries on the tasks that do the work, and never on a run_job_task, because
    Databricks drops task-level retry policy there;
  * no two jobs starting the same pipeline. Pipeline 3 defines no pipelines, so this
    is checked as "no pipeline_task at all" rather than assumed.

Usage:
    python3 databricks/migration/p3/recon/audit_job_graph.py [--json out.json]

Exits non-zero if any rule is violated.
"""
import argparse
import json
import sys

from databricks.sdk import WorkspaceClient

EXPECTED = {
    "ow_tp_p3_analytics_daily": "0 0 2 * * ?",
    "ow_tp_p3_storage_cleanup_daily": "0 30 2 * * ?",
    "ow_tp_p3_audit_archive_weekly": "0 0 3 ? * SUN",
    "ow_tp_p3_usage_rollup_daily": "0 0 2 * * ?",
    "ow_tp_p3_user_activity_daily": "0 0 5 * * ?",
}


def collect(w):
    """Return {bare job name: settings dict} for every deployed pipeline-3 job.

    Development-mode deploys prefix the resource name with "[dev <principal>] ", so the
    deployed name is matched on its suffix rather than compared for equality.
    """
    found = {}
    for listed in w.jobs.list():
        name = listed.settings.name or ""
        bare = next((b for b in EXPECTED if name.endswith(b)), None)
        if bare is None:
            continue
        s = w.jobs.get(listed.job_id).settings
        tasks = {}
        for t in s.tasks or []:
            tasks[t.task_key] = {
                "kind": (
                    "run_job_task" if t.run_job_task
                    else "pipeline_task" if t.pipeline_task
                    else "spark_python_task" if t.spark_python_task
                    else "other"
                ),
                "depends_on": sorted(d.task_key for d in (t.depends_on or [])),
                "max_retries": t.max_retries,
                "new_cluster": bool(t.new_cluster),
                "existing_cluster_id": t.existing_cluster_id,
                "environment_key": t.environment_key,
                "target_job_id": t.run_job_task.job_id if t.run_job_task else None,
                "pipeline_id": t.pipeline_task.pipeline_id if t.pipeline_task else None,
            }
        found[bare] = {
            "deployed_name": name,
            "job_id": listed.job_id,
            "cron": s.schedule.quartz_cron_expression if s.schedule else None,
            "pause_status": s.schedule.pause_status.value if s.schedule else None,
            "max_concurrent_runs": s.max_concurrent_runs,
            "queue": bool(s.queue and s.queue.enabled),
            "timeout_seconds": s.timeout_seconds,
            "job_clusters": len(s.job_clusters or []),
            "tasks": tasks,
        }
    return found


def check(found):
    problems = []
    for name, cron in EXPECTED.items():
        job = found.get(name)
        if job is None:
            problems.append(f"{name}: not deployed")
            continue
        if job["cron"] != cron:
            problems.append(f"{name}: cron is {job['cron']}, expected {cron}")
        if job["pause_status"] != "PAUSED":
            problems.append(f"{name}: schedule is {job['pause_status']}, expected PAUSED")
        if job["max_concurrent_runs"] != 1:
            problems.append(f"{name}: max_concurrent_runs is {job['max_concurrent_runs']}")
        if not job["queue"]:
            problems.append(f"{name}: queueing is off")
        if job["job_clusters"]:
            problems.append(f"{name}: defines {job['job_clusters']} job cluster(s)")
        for key, t in job["tasks"].items():
            where = f"{name}.{key}"
            if t["new_cluster"] or t["existing_cluster_id"]:
                problems.append(f"{where}: runs on a cluster, not serverless")
            if t["pipeline_id"]:
                problems.append(f"{where}: starts a pipeline; pipeline 3 defines none")
            if t["kind"] == "run_job_task":
                if t["max_retries"]:
                    problems.append(
                        f"{where}: asserts max_retries on a run_job_task, which Databricks drops"
                    )
            elif t["max_retries"] != 2:
                problems.append(f"{where}: max_retries is {t['max_retries']}, expected 2")

    # A run_job_task must point at another pipeline-3 job, not duplicate its tasks.
    ids = {j["job_id"]: n for n, j in found.items()}
    for name, job in found.items():
        for key, t in job["tasks"].items():
            if t["kind"] == "run_job_task" and t["target_job_id"] not in ids:
                problems.append(
                    f"{name}.{key}: run_job_task points at job {t['target_job_id']}, "
                    "which is not a pipeline-3 job"
                )
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write the collected job graph here")
    args = ap.parse_args()

    found = collect(WorkspaceClient())
    problems = check(found)

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(found, fh, indent=2, sort_keys=True)

    for name in EXPECTED:
        job = found.get(name)
        if job is None:
            continue
        edges = [
            f"{k} -> job {t['target_job_id']}"
            for k, t in job["tasks"].items()
            if t["kind"] == "run_job_task"
        ]
        print(
            f"{name}: {job['cron']} {job['pause_status']} "
            f"conc={job['max_concurrent_runs']} queue={job['queue']} "
            f"clusters={job['job_clusters']} tasks={len(job['tasks'])}"
            + (f" edges={edges}" if edges else "")
        )

    if problems:
        print("\nFAIL")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\nOK: schedules paused, serverless only, retries on owning tasks, no pipeline starts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
