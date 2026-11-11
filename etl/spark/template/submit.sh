#!/usr/bin/env bash
# run_token=dbx-d1111 expires=2026-11-24
# Common Spark template submit wrapper.
#   submit.sh --job <id> --output <area>/<name> -- <spark-submit args...>
# - Properties: etl/spark/conf/spark-defaults.conf + spark-defaults.template.conf (AQE, retries,
#   partition sizing, dynamic partition overwrite).
# - Idempotent output: the job runs with LAKE_DIR=<lake>/.staging/<job>/<run>; on success the
#   staged <area>/<name> directory becomes a new version under <lake>/.versions/<job>/ and
#   <lake>/<area>/<name> (a relative symlink) is switched to it with one atomic rename. Failed attempts
#   leave the published output untouched. Only the previous version is kept.
# - Retries: the whole application is retried SPARK_TEMPLATE_RETRIES times (default 2) after
#   SPARK_TEMPLATE_RETRY_DELAY seconds (default 60).
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
job="" output=""
while [ $# -gt 0 ]; do
    case "$1" in
        --job) job=$2; shift 2 ;;
        --output) output=$2; shift 2 ;;
        --) shift; break ;;
        *) echo "unknown option $1" >&2; exit 2 ;;
    esac
done
[ -n "$job" ] && [ -n "$output" ] || { echo "--job and --output are required" >&2; exit 2; }
lake=${LAKE_ROOT:-/opt/lake}
spark_submit=${SPARK_SUBMIT:-/opt/spark/bin/spark-submit}
retries=${SPARK_TEMPLATE_RETRIES:-2}
delay=${SPARK_TEMPLATE_RETRY_DELAY:-60}
run_id=$(date -u +%Y%m%dT%H%M%SZ)-$$
props=$(mktemp)
trap 'rm -f "$props"' EXIT
cat "${SPARK_CONF_DIR:-$here/../conf}/spark-defaults.conf" "$here/spark-defaults.template.conf" > "$props"

attempt=0
while :; do
    staging="$lake/.staging/$job/$run_id-$attempt"
    rm -rf "$staging"; mkdir -p "$staging"
    if LAKE_DIR="$staging" "$spark_submit" --properties-file "$props" \
        --conf "spark.app.name=$job" "$@"; then
        break
    fi
    rm -rf "$staging"
    if [ "$attempt" -ge "$retries" ]; then
        echo "TEMPLATE job=$job failed after $((attempt + 1)) attempts" >&2; exit 1
    fi
    attempt=$((attempt + 1))
    echo "TEMPLATE job=$job retry $attempt/$retries in ${delay}s" >&2
    sleep "$delay"
done

[ -d "$staging/$output" ] || { echo "TEMPLATE job=$job wrote no $output" >&2; rm -rf "$staging"; exit 1; }
versions="$lake/.versions/$job"
mkdir -p "$versions" "$(dirname "$lake/$output")"
mv "$staging/$output" "$versions/$run_id"
rm -rf "$lake/.staging/$job"
target="$lake/$output"
previous=""
if [ -L "$target" ]; then
    previous=$(basename "$(readlink "$target")")
elif [ -d "$target" ]; then
    previous=legacy-$run_id
    mv "$target" "$versions/$previous"
fi
ln -s "$(realpath -m --relative-to="$(dirname "$target")" "$versions/$run_id")" "$target.$run_id.link"
mv -T "$target.$run_id.link" "$target"
for old in "$versions"/*; do
    case "${old##*/}" in "$run_id"|"$previous") ;; *) rm -rf "$old" ;; esac
done
echo "TEMPLATE job=$job attempts=$((attempt + 1)) published=$versions/$run_id previous=${previous:-none}"
