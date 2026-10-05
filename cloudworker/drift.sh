#!/usr/bin/env bash
# Compare Terraform-owned SQS queues with AWS. Usage: cloudworker/drift.sh [--json]
set -euo pipefail

usage() {
  printf 'usage: cloudworker/drift.sh [--json]\n' >&2
}

json_output=0
for arg in "$@"; do
  case "$arg" in
    --json) json_output=1 ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      printf 'cloudworker/drift.sh: unexpected argument: %s\n' "$arg" >&2
      exit 2
      ;;
  esac
done

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/.." && pwd)"
export CW_DRIFT_ROOT="$ROOT"
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="$AWS_REGION"
export AWS_PAGER=""

if ! command -v python3 >/dev/null 2>&1; then
  printf 'cloudworker/drift.sh: python3 is required\n' >&2
  exit 2
fi
if [[ "$json_output" == 0 ]] && ! command -v column >/dev/null 2>&1; then
  printf 'cloudworker/drift.sh: column is required for table output\n' >&2
  exit 2
fi

set +e
result="$(CW_DRIFT_JSON="$json_output" python3 - <<'PY'
import json
import os
import re
import subprocess
import sys
from pathlib import Path


class DriftError(Exception):
    pass


ATTRIBUTE_ORDER = [
    "MessageRetentionPeriod",
    "VisibilityTimeout",
    "ReceiveMessageWaitTimeSeconds",
    "RedrivePolicy",
    "SSE",
]
ATTRIBUTE_DEFAULTS = {
    "message_retention_seconds": (345600, "MessageRetentionPeriod"),
    "visibility_timeout_seconds": (30, "VisibilityTimeout"),
    "receive_wait_time_seconds": (0, "ReceiveMessageWaitTimeSeconds"),
}
QUEUE_PREFIX = "otterworks-"


def redact(value):
    return re.sub(r"\b\d{12}\b", "<account>", str(value))


def matching_brace(source, opening):
    depth = 0
    in_string = False
    escaped = False
    line_comment = False
    block_comment = False
    index = opening

    while index < len(source):
        char = source[index]
        next_char = source[index + 1] if index + 1 < len(source) else ""

        if line_comment:
            if char == "\n":
                line_comment = False
        elif block_comment:
            if char == "*" and next_char == "/":
                block_comment = False
                index += 1
        elif in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "#":
            line_comment = True
        elif char == "/" and next_char == "/":
            line_comment = True
            index += 1
        elif char == "/" and next_char == "*":
            block_comment = True
            index += 1
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index

        index += 1

    raise DriftError("unterminated HCL block")


def find_blocks(source, pattern, description):
    blocks = []
    for match in re.finditer(pattern, source, re.MULTILINE):
        opening = match.end() - 1
        closing = matching_brace(source, opening)
        blocks.append(
            {
                "match": match,
                "opening": opening,
                "closing": closing,
                "text": source[match.start():closing + 1],
                "line": source.count("\n", 0, match.start()) + 1,
            }
        )
    if not blocks:
        raise DriftError(f"no {description} found")
    return blocks


def strip_comment(line, in_block_comment=False):
    result = []
    in_string = False
    escaped = False
    index = 0

    while index < len(line):
        char = line[index]
        next_char = line[index + 1] if index + 1 < len(line) else ""

        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                index += 1
        elif in_string:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
            result.append(char)
        elif char == "#":
            break
        elif char == "/" and next_char == "/":
            break
        elif char == "/" and next_char == "*":
            in_block_comment = True
            index += 1
        else:
            result.append(char)
        index += 1

    return "".join(result), in_block_comment


def update_depth(line, depth, in_block_comment=False):
    in_string = False
    escaped = False
    index = 0

    while index < len(line):
        char = line[index]
        next_char = line[index + 1] if index + 1 < len(line) else ""

        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                index += 1
        elif in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "#":
            break
        elif char == "/" and next_char == "/":
            break
        elif char == "/" and next_char == "*":
            in_block_comment = True
            index += 1
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        index += 1

    return depth, in_block_comment


def assignments(source, block):
    body = source[block["opening"] + 1:block["closing"]]
    line_number = source.count("\n", 0, block["opening"])
    depth = 1
    in_block_comment = False
    found = {}

    for line in body.splitlines():
        line_number += 1
        cleaned, comment_state = strip_comment(line, in_block_comment)
        if depth == 1:
            match = re.match(r"^\s*([A-Za-z_]\w*)\s*=\s*(.*?)\s*$", cleaned)
            if match:
                key = match.group(1)
                if key in found:
                    raise DriftError(f"duplicate HCL assignment {key} at line {line_number}")
                found[key] = {"value": match.group(2), "line": line_number}
        depth, in_block_comment = update_depth(line, depth, in_block_comment)
        if comment_state != in_block_comment:
            in_block_comment = comment_state

    return found


def required_assignment(values, key, description):
    if key not in values:
        raise DriftError(f"missing {key} in {description}")
    return values[key]


def literal_string(raw, description):
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as error:
        raise DriftError(f"cannot resolve {description}: {raw}") from error
    if not isinstance(value, str):
        raise DriftError(f"expected a string for {description}")
    return value


def read_file(root, relative):
    path = root / relative
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise DriftError(f"cannot read {relative}: {error}") from error


def resolve_main_name(raw, project, environment):
    name = literal_string(raw, "main queue name")
    name = name.replace("${var.project}", project)
    name = name.replace("${var.environment}", environment)
    if "${" in name:
        raise DriftError(f"unresolved interpolation in main queue name: {name}")
    return name


def resolve_cloud_worker_name(raw, locals_values):
    match = re.fullmatch(r"local\.([A-Za-z_]\w*)", raw)
    if not match:
        raise DriftError(f"cannot resolve cloud-worker queue name: {raw}")
    key = match.group(1)
    if key not in locals_values:
        raise DriftError(f"unresolved local.{key} in cloud-worker queue name")
    return literal_string(locals_values[key]["value"], f"local.{key}")


def parse_redrive(block, assignments_by_name, root_name):
    match = re.search(
        r"\bdeadLetterTargetArn\s*=\s*aws_sqs_queue\.([A-Za-z_][\w-]*)\.arn\b",
        block["text"],
    )
    count = re.search(r"\bmaxReceiveCount\s*=\s*(\d+)\b", block["text"])
    if not match or not count:
        raise DriftError(f"cannot parse redrive_policy for {root_name}")
    target = match.group(1)
    if target not in assignments_by_name:
        raise DriftError(f"unresolved aws_sqs_queue.{target} redrive target in {root_name}")
    return f"{assignments_by_name[target]['name']}/maxReceiveCount={count.group(1)}"


def terraform_queues(root):
    definitions = []

    main_path = "infrastructure/terraform/main.tf"
    module_source = read_file(root, main_path)
    messaging_modules = find_blocks(
        module_source,
        r'(?m)^[ \t]*module\s+"messaging"\s*\{',
        'module "messaging" block',
    )
    if len(messaging_modules) != 1:
        raise DriftError(f"expected one module 'messaging' block in {main_path}")
    project = literal_string(
        required_assignment(
            assignments(module_source, messaging_modules[0]),
            "project",
            f'module "messaging" in {main_path}',
        )["value"],
        "module messaging project",
    )

    variables_path = "infrastructure/terraform/variables.tf"
    variables_source = read_file(root, variables_path)
    environment_blocks = find_blocks(
        variables_source,
        r'(?m)^[ \t]*variable\s+"environment"\s*\{',
        'variable "environment" block',
    )
    if len(environment_blocks) != 1:
        raise DriftError(f"expected one variable 'environment' block in {variables_path}")
    default_environment = literal_string(
        required_assignment(
            assignments(variables_source, environment_blocks[0]),
            "default",
            f'variable "environment" in {variables_path}',
        )["value"],
        "variable environment default",
    )
    environment = os.environ.get("CW_DRIFT_ENVIRONMENT", default_environment)
    if not environment:
        raise DriftError("CW_DRIFT_ENVIRONMENT must not be empty")

    main_queue_path = "infrastructure/terraform/modules/messaging/main.tf"
    main_queue_source = read_file(root, main_queue_path)
    main_blocks = find_blocks(
        main_queue_source,
        r'(?m)^[ \t]*resource\s+"aws_sqs_queue"\s+"([^"]+)"\s*\{',
        f'aws_sqs_queue resource in {main_queue_path}',
    )
    main_resources = []
    for block in main_blocks:
        values = assignments(main_queue_source, block)
        name_value = required_assignment(values, "name", f"resource at {main_queue_path}:{block['line']}")
        main_resources.append(
            {
                "label": block["match"].group(1),
                "name": resolve_main_name(name_value["value"], project, environment),
                "path": main_queue_path,
                "line": block["line"],
                "values": values,
                "text": block["text"],
                "root": "main",
            }
        )

    cloud_main_path = "infrastructure/terraform/cloud-worker/main.tf"
    cloud_main_source = read_file(root, cloud_main_path)
    locals_blocks = find_blocks(
        cloud_main_source,
        r"(?m)^[ \t]*locals\s*\{",
        f"locals block in {cloud_main_path}",
    )
    local_values = {}
    for block in locals_blocks:
        local_values.update(assignments(cloud_main_source, block))

    cloud_queue_path = "infrastructure/terraform/cloud-worker/messaging.tf"
    cloud_queue_source = read_file(root, cloud_queue_path)
    cloud_blocks = find_blocks(
        cloud_queue_source,
        r'(?m)^[ \t]*resource\s+"aws_sqs_queue"\s+"([^"]+)"\s*\{',
        f'aws_sqs_queue resource in {cloud_queue_path}',
    )
    cloud_resources = []
    for block in cloud_blocks:
        values = assignments(cloud_queue_source, block)
        name_value = required_assignment(values, "name", f"resource at {cloud_queue_path}:{block['line']}")
        cloud_resources.append(
            {
                "label": block["match"].group(1),
                "name": resolve_cloud_worker_name(name_value["value"], local_values),
                "path": cloud_queue_path,
                "line": block["line"],
                "values": values,
                "text": block["text"],
                "root": "cloud-worker",
            }
        )

    result = []
    for root_name, resources in (("main", main_resources), ("cloud-worker", cloud_resources)):
        labels = {resource["label"]: resource for resource in resources}
        for resource in resources:
            if resource["name"].startswith(QUEUE_PREFIX) is False:
                continue
            queue = {
                **resource,
                "root": root_name,
                "attributes": {},
            }
            values = resource["values"]
            for hcl_name in ATTRIBUTE_DEFAULTS:
                if hcl_name in values:
                    raw = values[hcl_name]["value"]
                    if not re.fullmatch(r"\d+", raw):
                        raise DriftError(f"cannot parse {hcl_name} for {resource['name']}: {raw}")
                    queue["attributes"][hcl_name] = {
                        "value": str(int(raw)),
                        "display": str(int(raw)),
                        "line": values[hcl_name]["line"],
                    }
                else:
                    default_value, _ = ATTRIBUTE_DEFAULTS[hcl_name]
                    queue["attributes"][hcl_name] = {
                        "value": str(default_value),
                        "display": f"{default_value} (default)",
                        "line": resource["line"],
                    }

            if "redrive_policy" in values:
                redrive = parse_redrive(resource, labels, root_name)
                queue["attributes"]["redrive_policy"] = {
                    "value": redrive,
                    "display": redrive,
                    "line": values["redrive_policy"]["line"],
                }
            else:
                queue["attributes"]["redrive_policy"] = {
                    "value": "none",
                    "display": "none",
                    "line": resource["line"],
                }

            if "kms_master_key_id" in values:
                raw = values["kms_master_key_id"]["value"]
                try:
                    key_id = literal_string(raw, f"kms_master_key_id for {resource['name']}")
                except DriftError:
                    key_id = raw
                if key_id:
                    sse = "SSE-KMS"
                else:
                    sse = "off"
                sse_line = values["kms_master_key_id"]["line"]
                sse_display = sse
            elif "sqs_managed_sse_enabled" in values:
                raw = values["sqs_managed_sse_enabled"]["value"]
                if raw == "true":
                    sse = "SSE-SQS"
                elif raw == "false":
                    sse = "off"
                else:
                    raise DriftError(f"cannot parse sqs_managed_sse_enabled for {resource['name']}: {raw}")
                sse_line = values["sqs_managed_sse_enabled"]["line"]
                sse_display = sse
            else:
                sse = "SSE-SQS"
                sse_line = resource["line"]
                sse_display = "SSE-SQS (default)"
            queue["attributes"]["sse"] = {
                "value": sse,
                "display": sse_display,
                "line": sse_line,
            }
            result.append(queue)

    names = [queue["name"] for queue in result]
    if len(names) != len(set(names)):
        raise DriftError("duplicate SQS queue names across Terraform roots")
    return result


def run_aws(arguments):
    completed = subprocess.run(
        ["aws", *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise DriftError(f"AWS command failed: {redact(detail)}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise DriftError(f"AWS command returned invalid JSON: {error}") from error


def live_queues():
    fixture = os.environ.get("CW_DRIFT_LIVE_FILE")
    if fixture:
        try:
            data = json.loads(Path(fixture).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise DriftError(f"cannot read CW_DRIFT_LIVE_FILE: {error}") from error
        if not isinstance(data, dict) or any(not isinstance(value, dict) for value in data.values()):
            raise DriftError("CW_DRIFT_LIVE_FILE must map queue names to Attributes maps")
        return {name: attributes for name, attributes in data.items() if name.startswith(QUEUE_PREFIX)}

    listing = run_aws(
        ["sqs", "list-queues", "--queue-name-prefix", QUEUE_PREFIX, "--output", "json"]
    )
    urls = listing.get("QueueUrls", [])
    if not isinstance(urls, list):
        raise DriftError("aws sqs list-queues returned an invalid QueueUrls value")
    queues = {}
    for url in urls:
        if not isinstance(url, str) or not url:
            raise DriftError("aws sqs list-queues returned an invalid queue URL")
        name = url.rstrip("/").rsplit("/", 1)[-1]
        if not name.startswith(QUEUE_PREFIX):
            continue
        attributes_result = run_aws(
            [
                "sqs",
                "get-queue-attributes",
                "--queue-url",
                url,
                "--attribute-names",
                "All",
                "--output",
                "json",
            ]
        )
        attributes = attributes_result.get("Attributes")
        if not isinstance(attributes, dict):
            raise DriftError(f"aws sqs get-queue-attributes returned no Attributes for {name}")
        queues[name] = attributes
    return queues


def live_redrive(attributes, queue_name):
    raw = attributes.get("RedrivePolicy")
    if not raw:
        return "none"
    try:
        policy = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as error:
        raise DriftError(f"invalid live RedrivePolicy for {queue_name}: {error}") from error
    arn = policy.get("deadLetterTargetArn")
    count = policy.get("maxReceiveCount")
    if not isinstance(arn, str) or count is None:
        raise DriftError(f"incomplete live RedrivePolicy for {queue_name}")
    return f"{arn.rsplit(':', 1)[-1]}/maxReceiveCount={count}"


def live_values(attributes, queue_name):
    values = {}
    for hcl_name, (default_value, live_name) in ATTRIBUTE_DEFAULTS.items():
        raw = attributes.get(live_name)
        if raw is None:
            values[live_name] = "-"
        else:
            try:
                values[live_name] = str(int(raw))
            except (TypeError, ValueError) as error:
                raise DriftError(f"invalid {live_name} for {queue_name}: {raw}") from error
    values["RedrivePolicy"] = live_redrive(attributes, queue_name)
    if attributes.get("KmsMasterKeyId"):
        values["SSE"] = "SSE-KMS"
    elif attributes.get("SqsManagedSseEnabled") == "true":
        values["SSE"] = "SSE-SQS"
    else:
        values["SSE"] = "off"
    return values


def make_rows(terraform, live):
    rows = []
    terraform_by_name = {queue["name"]: queue for queue in terraform}

    for queue in terraform:
        name = queue["name"]
        if name not in live:
            name_line = queue["values"]["name"]["line"]
            rows.append(
                {
                    "queue": name,
                    "attribute": "-",
                    "live": "-",
                    "git": "-",
                    "root": queue["root"],
                    "file_line": f"{queue['path']}:{name_line}",
                    "status": "MISSING",
                }
            )
            continue

        actual_values = live_values(live[name], name)
        attribute_map = {
            "MessageRetentionPeriod": "message_retention_seconds",
            "VisibilityTimeout": "visibility_timeout_seconds",
            "ReceiveMessageWaitTimeSeconds": "receive_wait_time_seconds",
            "RedrivePolicy": "redrive_policy",
            "SSE": "sse",
        }
        for attribute in ATTRIBUTE_ORDER:
            git_attribute = queue["attributes"][attribute_map[attribute]]
            actual = actual_values[attribute]
            rows.append(
                {
                    "queue": name,
                    "attribute": attribute,
                    "live": actual,
                    "git": git_attribute["display"],
                    "root": queue["root"],
                    "file_line": f"{queue['path']}:{git_attribute['line']}",
                    "status": "ok" if actual == git_attribute["value"] else "DRIFT",
                }
            )

    for name in live:
        if name not in terraform_by_name:
            rows.append(
                {
                    "queue": name,
                    "attribute": "-",
                    "live": "-",
                    "git": "-",
                    "root": "none",
                    "file_line": "-",
                    "status": "UNOWNED",
                }
            )

    root_order = {"cloud-worker": 0, "main": 1, "none": 2}
    attribute_order = {name: index for index, name in enumerate(ATTRIBUTE_ORDER)}
    rows.sort(
        key=lambda row: (
            root_order[row["root"]],
            row["queue"],
            attribute_order.get(row["attribute"], -1),
        )
    )
    return rows


def main():
    root = Path(os.environ["CW_DRIFT_ROOT"])
    live = live_queues()
    terraform = terraform_queues(root)
    rows = make_rows(terraform, live)
    drift_rows = [row for row in rows if row["status"] == "DRIFT"]
    missing = sum(row["status"] == "MISSING" for row in rows)
    unowned = sorted(row["queue"] for row in rows if row["status"] == "UNOWNED")
    summary = {
        "drift_attributes": len(drift_rows),
        "drift_queues": len({row["queue"] for row in drift_rows}),
        "missing": missing,
        "unowned": unowned,
    }

    if os.environ.get("CW_DRIFT_JSON") == "1":
        print(json.dumps({"rows": rows, "summary": summary}, separators=(",", ":")))
        return 1 if drift_rows or missing else 0

    print("\t".join(["QUEUE", "ATTRIBUTE", "LIVE", "GIT", "ROOT", "FILE:LINE", "STATUS"]))
    for row in rows:
        print(
            "\t".join(
                [
                    row["queue"],
                    row["attribute"],
                    row["live"],
                    row["git"],
                    row["root"],
                    row["file_line"],
                    row["status"],
                ]
            )
        )
    names = ",".join(unowned) if unowned else "-"
    print(
        f"drift: {summary['drift_attributes']} attribute(s) on "
        f"{summary['drift_queues']} queue(s); missing: {summary['missing']}; "
        f"unowned: {len(unowned)} ({names})"
    )
    return 1 if drift_rows or missing else 0


try:
    sys.exit(main())
except DriftError as error:
    print(f"cloudworker/drift.sh: {redact(error)}", file=sys.stderr)
    sys.exit(2)
except (OSError, KeyError, TypeError, ValueError) as error:
    print(f"cloudworker/drift.sh: {redact(error)}", file=sys.stderr)
    sys.exit(2)
PY
)"
status=$?
set -e

if [[ "$status" -ge 2 ]]; then
  exit "$status"
fi

if [[ "$json_output" == 1 ]]; then
  printf '%s\n' "$result" | sed -E 's/[0-9]{12}/<account>/g'
else
  summary="${result##*$'\n'}"
  table="${result%$'\n'*}"
  printf '%s\n' "$table" | column -t -s $'\t' | sed -E 's/[0-9]{12}/<account>/g'
  printf '\n%s\n' "$summary" | sed -E 's/[0-9]{12}/<account>/g'
fi

exit "$status"
