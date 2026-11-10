#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/../.."
ns=${NS:-sfx-d1110-before}
limit=${SPARK_JOBS:-30}
mkdir -p etl/spark/.data/logs
mapfile -t jobs < <(python3 -c 'import json,pathlib; entries=[json.loads(p.read_text()) for p in sorted(pathlib.Path("etl/spark/jobs/registry").glob("*.yaml"))]; [print(e["job"]) for e in entries if e["status"] != "snowflake"]')
if [ -n "${JOB:-}" ]; then
    found=0
    for job in "${jobs[@]}"; do
        if [ "$job" = "$JOB" ]; then found=1; fi
    done
    if [ "$found" = 0 ]; then echo "Unknown JOB: $JOB" >&2; exit 2; fi
    jobs=("$JOB")
else
    if ! [[ "$limit" =~ ^[0-9]+$ ]]; then echo "SPARK_JOBS must be a nonnegative integer" >&2; exit 2; fi
    jobs=("${jobs[@]:0:limit}")
fi
failed=0
summary=etl/spark/.data/logs/status.tsv
printf '%-36s %-8s %s\n' JOB STATUS SECONDS > "$summary"
for job in "${jobs[@]}"; do
    start=$SECONDS
    status_kind=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "etl/spark/jobs/registry/$job.yaml")
    script="/opt/sfx/spark/submit/$job.sh"
    args=()
    if [ "$status_kind" = template ]; then
        script=/opt/sfx/spark/template/submit.sh
        args=("$job")
    fi
    if docker compose -f docker-compose.spark.yml -p "sfx-d1110-spark-$ns" exec -T spark-master \
        bash "$script" "${args[@]}" > "etl/spark/.data/logs/$job.log" 2>&1; then
        status=OK
    else
        status=FAILED
        failed=1
    fi
    printf '%-36s %-8s %s\n' "$job" "$status" "$((SECONDS - start))" | tee -a "$summary"
done
printf '\n'
cat "$summary"
exit "$failed"
