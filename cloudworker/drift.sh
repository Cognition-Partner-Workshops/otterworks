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
from decimal import Decimal, InvalidOperation


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
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise DriftError(f"AWS command returned invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise DriftError("AWS command returned a non-object JSON value")
    return value


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


SECTION_NAMES = {"sqs", "sns", "dynamodb", "alarms"}
KIND_ORDER = {"sqs": 0, "sns": 1, "sns-sub": 2, "dynamodb": 3, "alarm": 4}
KIND_ATTRIBUTES = {
    "sqs": ATTRIBUTE_ORDER,
    "sns": ["DeliveryPolicy", "Subscriptions"],
    "sns-sub": ["RawMessageDelivery", "FilterPolicy", "DeliveryPolicy"],
    "dynamodb": ["BillingMode", "KeySchema", "TTL", "PointInTimeRecovery"],
    "alarm": [
        "Metric",
        "Dimensions",
        "Statistic",
        "ComparisonOperator",
        "Period",
        "Threshold",
        "EvaluationPeriods",
        "ActionsEnabled",
    ],
}
CW_PREFIX = "otterworks-cw-"


class HclValueParser:
    def __init__(self, source):
        token_pattern = re.compile(
            r'\s+|//[^\n]*|#[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|'
            r'[A-Za-z_][A-Za-z0-9_-]*|-?\d+(?:\.\d+)?|[{}\[\]=,:().]',
            re.DOTALL,
        )
        self.tokens = [
            match.group(0)
            for match in token_pattern.finditer(source)
            if not match.group(0).isspace()
            and not match.group(0).startswith(("//", "#", "/*"))
        ]
        self.index = 0

    def peek(self):
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def take(self):
        token = self.peek()
        if token is None:
            raise DriftError("incomplete HCL value")
        self.index += 1
        return token

    def parse(self):
        value = self.value()
        if self.peek() is not None:
            raise DriftError(f"unsupported HCL value near {self.peek()}")
        return value

    def value(self):
        token = self.take()
        if token == "{":
            result = {}
            while self.peek() != "}":
                if self.peek() is None:
                    raise DriftError("unterminated HCL object")
                key = self.take()
                if key.startswith('"'):
                    key = json.loads(key)
                if self.take() not in ("=", ":"):
                    raise DriftError("expected = in HCL object")
                if key in result:
                    raise DriftError(f"duplicate HCL object key {key}")
                result[key] = self.value()
                if self.peek() == ",":
                    self.take()
            self.take()
            return result
        if token == "[":
            result = []
            while self.peek() != "]":
                if self.peek() is None:
                    raise DriftError("unterminated HCL list")
                result.append(self.value())
                if self.peek() == ",":
                    self.take()
                elif self.peek() != "]":
                    raise DriftError("expected , in HCL list")
            self.take()
            return result
        if token.startswith('"'):
            return json.loads(token)
        if re.fullmatch(r"-?\d+", token):
            return int(token)
        if re.fullmatch(r"-?\d+\.\d+", token):
            return float(token)
        if token in ("true", "false", "null"):
            return {"true": True, "false": False, "null": None}[token]
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", token):
            parts = [token]
            while self.peek() == ".":
                self.take()
                parts.append(self.take())
            return ".".join(parts)
        raise DriftError(f"unsupported HCL value token {token}")


def raw_assignment(source, assignment):
    lines = source.splitlines()
    line_index = assignment["line"] - 1
    line = lines[line_index]
    match = re.match(r"^\s*[A-Za-z_]\w*\s*=\s*(.*?)\s*$", line)
    if not match:
        raise DriftError(f"cannot read assignment at line {assignment['line']}")
    raw = match.group(1)
    heredoc = re.match(r"<<-?\s*([A-Za-z_]\w*)\s*$", raw)
    if heredoc:
        delimiter = heredoc.group(1)
        body = []
        for candidate in lines[line_index + 1:]:
            if candidate.strip() == delimiter:
                return "\n".join(body)
            body.append(candidate)
        raise DriftError(f"unterminated heredoc at line {assignment['line']}")

    wrapped = re.match(r"^jsonencode\s*\(", raw)
    opening = raw.find("{") if wrapped else (0 if raw.startswith("{") else -1)
    if opening >= 0:
        absolute = sum(len(item) + 1 for item in lines[:line_index]) + match.start(1) + opening
        closing = matching_brace(source, absolute)
        expression = source[sum(len(item) + 1 for item in lines[:line_index]) + match.start(1):closing + 1]
        return expression + (")" if wrapped else "")
    return raw


def parse_hcl_expression(raw, description):
    expression = raw.strip()
    if expression.startswith("jsonencode"):
        match = re.fullmatch(r"jsonencode\s*\((.*)\)\s*", expression, re.DOTALL)
        if not match:
            raise DriftError(f"cannot parse {description}: {raw}")
        expression = match.group(1)
    try:
        return HclValueParser(expression).parse()
    except (json.JSONDecodeError, DriftError) as error:
        raise DriftError(f"cannot parse {description}: {raw}") from error


def canonical_json_value(value, description):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            raise DriftError(f"invalid JSON for {description}: {error}") from error
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as error:
        raise DriftError(f"invalid JSON for {description}: {error}") from error


def policy_attribute(source, values, key, description, default_display=None):
    if key not in values:
        return {
            "value": "none",
            "display": default_display or "none (default)",
            "line": None,
        }
    raw = raw_assignment(source, values[key])
    if raw.startswith('"'):
        raw = literal_string(raw, description)
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as error:
            raise DriftError(f"invalid JSON for {description}: {error}") from error
    elif raw.lstrip().startswith("{") or raw.lstrip().startswith("jsonencode"):
        value = parse_hcl_expression(raw, description)
    else:
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as error:
            raise DriftError(f"cannot parse {description}: {raw}") from error
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return {"value": rendered, "display": rendered, "line": values[key]["line"]}


def bool_value(raw, description):
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str) and raw.lower() in ("true", "false"):
        return raw.lower() == "true"
    raise DriftError(f"cannot parse boolean for {description}: {raw}")


def bool_attribute(source, values, key, description, default, default_display=None):
    if key not in values:
        return {
            "value": "true" if default else "false",
            "display": default_display or f"{str(default).lower()} (default)",
            "line": None,
        }
    raw = raw_assignment(source, values[key])
    value = bool_value(raw, description)
    rendered = str(value).lower()
    return {"value": rendered, "display": rendered, "line": values[key]["line"]}


def number_string(value, description):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise DriftError(f"invalid number for {description}: {value}") from error
    if not number.is_finite():
        raise DriftError(f"invalid number for {description}: {value}")
    if number == number.to_integral_value():
        return str(int(number))
    return format(number.normalize(), "f")


def nested_blocks(resource, block_name):
    blocks = []
    pattern = rf"(?m)^[ \t]*{re.escape(block_name)}\s*\{{"
    for match in re.finditer(pattern, resource["text"]):
        opening = match.end() - 1
        closing = matching_brace(resource["text"], opening)
        blocks.append(
            {
                "opening": opening,
                "closing": closing,
                "text": resource["text"][match.start():closing + 1],
                "line": resource["line"] + resource["text"].count("\n", 0, match.start()),
            }
        )
    return blocks


def terraform_cloud_resources(root, queue_names):
    locals_values = {}
    main_path = "infrastructure/terraform/cloud-worker/main.tf"
    main_source = read_file(root, main_path)
    for block in find_blocks(main_source, r"(?m)^[ \t]*locals\s*\{", f"locals block in {main_path}"):
        locals_values.update(assignments(main_source, block))

    definitions = {kind: [] for kind in ("sns", "sns-sub", "dynamodb", "alarm")}
    resource_types = {
        "aws_sns_topic": "sns",
        "aws_sns_topic_subscription": "sns-sub",
        "aws_dynamodb_table": "dynamodb",
        "aws_cloudwatch_metric_alarm": "alarm",
    }
    sources = {}
    for path in sorted((root / "infrastructure/terraform/cloud-worker").glob("*.tf")):
        relative = str(path.relative_to(root))
        source = read_file(root, relative)
        sources[relative] = source
        for terraform_type, kind in resource_types.items():
            pattern = rf'(?m)^[ \t]*resource\s+"{terraform_type}"\s+"([^"]+)"\s*\{{'
            if not re.search(pattern, source):
                continue
            for block in find_blocks(source, pattern, f"{terraform_type} resource in {relative}"):
                values = assignments(source, block)
                definitions[kind].append(
                    {
                        "kind": kind,
                        "label": block["match"].group(1),
                        "path": relative,
                        "line": block["line"],
                        "values": values,
                        "text": block["text"],
                        "source": source,
                        "locals": locals_values,
                        "queue_names": queue_names,
                    }
                )

    def resolve_local(raw, description):
        match = re.fullmatch(r"local\.([A-Za-z_]\w*)", raw)
        if not match or match.group(1) not in locals_values:
            raise DriftError(f"cannot resolve {description}: {raw}")
        return literal_string(
            raw_assignment(main_source, locals_values[match.group(1)]),
            description,
        )

    def resolve_resource(resource, key):
        assignment = required_assignment(
            resource["values"],
            key,
            f"{resource['kind']} resource at {resource['path']}:{resource['line']}",
        )
        raw = raw_assignment(resource["source"], assignment)
        if re.fullmatch(r"local\.[A-Za-z_]\w*", raw):
            return resolve_local(raw, f"{key} for {resource['label']}")
        if raw.startswith('"'):
            return literal_string(raw, f"{key} for {resource['label']}")
        raise DriftError(f"cannot resolve {key} for {resource['label']}: {raw}")

    for resource in definitions["sns"]:
        resource["name"] = resolve_resource(resource, "name")
    for resource in definitions["dynamodb"]:
        resource["name"] = resolve_resource(resource, "name")
    for resource in definitions["alarm"]:
        resource["name"] = resolve_resource(resource, "alarm_name")

    topics_by_label = {item["label"]: item for item in definitions["sns"]}
    queues_by_label = {item["label"]: item for item in queue_names["cloud-worker"]}

    def resolve_reference(raw, description):
        match = re.fullmatch(r"aws_(sns_topic|sqs_queue)\.([A-Za-z_][\w-]*)\.(arn|name)", raw)
        if not match:
            raise DriftError(f"cannot resolve {description}: {raw}")
        terraform_type, label, attribute = match.groups()
        if terraform_type == "sns_topic" and attribute == "arn" and label in topics_by_label:
            return topics_by_label[label]["name"]
        if terraform_type == "sqs_queue" and label in queues_by_label:
            if attribute in ("arn", "name"):
                return queues_by_label[label]["name"]
        raise DriftError(f"unresolved {description}: {raw}")

    for resource in definitions["sns-sub"]:
        topic_raw = raw_assignment(resource["source"], required_assignment(resource["values"], "topic_arn", resource["label"]))
        topic_name = resolve_reference(topic_raw, f"topic_arn for {resource['label']}")
        protocol_raw = raw_assignment(resource["source"], required_assignment(resource["values"], "protocol", resource["label"]))
        protocol = literal_string(protocol_raw, f"protocol for {resource['label']}")
        endpoint_raw = raw_assignment(resource["source"], required_assignment(resource["values"], "endpoint", resource["label"]))
        if re.fullmatch(r"aws_(?:sns_topic|sqs_queue)\.[A-Za-z_][\w-]*\.(?:arn|name)", endpoint_raw):
            endpoint = resolve_reference(endpoint_raw, f"endpoint for {resource['label']}")
        else:
            endpoint = literal_string(endpoint_raw, f"endpoint for {resource['label']}")
        resource["topic_name"] = topic_name
        resource["protocol"] = protocol
        resource["endpoint"] = endpoint

    for resource in definitions["sns"]:
        values = resource["values"]
        delivery = policy_attribute(resource["source"], values, "delivery_policy", f"delivery_policy for {resource['name']}")
        if delivery["line"] is None:
            delivery["line"] = resource["line"]
        subscriptions = [item for item in definitions["sns-sub"] if item["topic_name"] == resource["name"]]
        rendered_subscriptions = sorted(f"{item['protocol']}:{short_endpoint(item['endpoint'])}" for item in subscriptions)
        resource["attributes"] = {
            "DeliveryPolicy": delivery,
            "Subscriptions": {
                "value": ",".join(rendered_subscriptions) if rendered_subscriptions else "none",
                "display": ",".join(rendered_subscriptions) if rendered_subscriptions else "none",
                "line": subscriptions[0]["line"] if subscriptions else resource["line"],
            },
        }

    for resource in definitions["sns-sub"]:
        values = resource["values"]
        raw_delivery = bool_attribute(
            resource["source"], values, "raw_message_delivery", f"raw_message_delivery for {resource['label']}", False
        )
        if raw_delivery["line"] is None:
            raw_delivery["line"] = resource["line"]
        filter_policy = policy_attribute(resource["source"], values, "filter_policy", f"filter_policy for {resource['label']}", "none (default)")
        delivery_policy = policy_attribute(resource["source"], values, "delivery_policy", f"delivery_policy for {resource['label']}", "none (default)")
        for item in (filter_policy, delivery_policy):
            if item["line"] is None:
                item["line"] = resource["line"]
        resource["name"] = f"{resource['topic_name']}/{resource['protocol']}:{short_endpoint(resource['endpoint'])}"
        resource["attributes"] = {
            "RawMessageDelivery": raw_delivery,
            "FilterPolicy": filter_policy,
            "DeliveryPolicy": delivery_policy,
        }

    for resource in definitions["dynamodb"]:
        values = resource["values"]
        hash_key = literal_string(
            raw_assignment(resource["source"], required_assignment(values, "hash_key", resource["name"])),
            f"hash_key for {resource['name']}",
        )
        range_key = None
        if "range_key" in values:
            range_key = literal_string(raw_assignment(resource["source"], values["range_key"]), f"range_key for {resource['name']}")
        attribute_types = {}
        for block in nested_blocks(resource, "attribute"):
            block_values = assignments(resource["text"], block)
            name = literal_string(raw_assignment(resource["text"], required_assignment(block_values, "name", resource["name"])), "DynamoDB attribute name")
            kind = literal_string(raw_assignment(resource["text"], required_assignment(block_values, "type", resource["name"])), f"type for {name}")
            attribute_types[name] = kind
        if hash_key not in attribute_types or (range_key and range_key not in attribute_types):
            raise DriftError(f"missing key attribute type for {resource['name']}")
        key_schema = f"HASH={hash_key}:{attribute_types[hash_key]}"
        if range_key:
            key_schema += f",RANGE={range_key}:{attribute_types[range_key]}"
        billing = resource["values"].get("billing_mode")
        if billing:
            billing_mode = literal_string(raw_assignment(resource["source"], billing), f"billing_mode for {resource['name']}")
            billing_display = billing_mode
            billing_line = billing["line"]
        else:
            billing_mode, billing_display, billing_line = "PROVISIONED", "PROVISIONED (default)", resource["line"]
        ttl_blocks = nested_blocks(resource, "ttl")
        ttl_value, ttl_display, ttl_line = "disabled", "disabled (default)", resource["line"]
        if ttl_blocks:
            if len(ttl_blocks) != 1:
                raise DriftError(f"expected one ttl block for {resource['name']}")
            block = ttl_blocks[0]
            nested_values = assignments(resource["text"], block)
            enabled = bool_value(raw_assignment(resource["text"], required_assignment(nested_values, "enabled", f"ttl for {resource['name']}")), "ttl enabled")
            ttl_line = block["line"]
            if enabled:
                attribute_name = literal_string(raw_assignment(resource["text"], required_assignment(nested_values, "attribute_name", f"ttl for {resource['name']}")), "ttl attribute_name")
                ttl_value = f"enabled ({attribute_name})"
                ttl_display = ttl_value
            else:
                ttl_value = ttl_display = "disabled"
        pitr_blocks = nested_blocks(resource, "point_in_time_recovery")
        pitr_value, pitr_display, pitr_line = "disabled", "disabled (default)", resource["line"]
        if pitr_blocks:
            if len(pitr_blocks) != 1:
                raise DriftError(f"expected one point_in_time_recovery block for {resource['name']}")
            nested_values = assignments(resource["text"], pitr_blocks[0])
            enabled = bool_value(raw_assignment(resource["text"], required_assignment(nested_values, "enabled", f"point_in_time_recovery for {resource['name']}")), "point_in_time_recovery enabled")
            pitr_value = pitr_display = "enabled" if enabled else "disabled"
            pitr_line = pitr_blocks[0]["line"]
        resource["attributes"] = {
            "BillingMode": {"value": billing_mode, "display": billing_display, "line": billing_line},
            "KeySchema": {"value": key_schema, "display": key_schema, "line": values["hash_key"]["line"]},
            "TTL": {"value": ttl_value, "display": ttl_display, "line": ttl_line},
            "PointInTimeRecovery": {"value": pitr_value, "display": pitr_display, "line": pitr_line},
        }

    for resource in definitions["alarm"]:
        values = resource["values"]
        def alarm_string(key):
            item = required_assignment(values, key, resource["name"])
            return literal_string(raw_assignment(resource["source"], item), f"{key} for {resource['name']}")

        metric = f"{alarm_string('namespace')}/{alarm_string('metric_name')}"
        dimensions_assignment = required_assignment(values, "dimensions", resource["name"])
        dimensions_raw = raw_assignment(resource["source"], dimensions_assignment)
        dimensions = parse_hcl_expression(dimensions_raw, f"dimensions for {resource['name']}")
        if not isinstance(dimensions, dict):
            raise DriftError(f"dimensions for {resource['name']} must be an object")
        resolved_dimensions = {}
        for key, value in dimensions.items():
            if isinstance(value, str) and re.fullmatch(r"aws_(?:sns_topic|sqs_queue)\.[A-Za-z_][\w-]*\.(?:arn|name)", value):
                value = resolve_reference(value, f"dimension {key} for {resource['name']}")
            if not isinstance(value, (str, int, float, bool)):
                raise DriftError(f"cannot resolve dimension {key} for {resource['name']}")
            resolved_dimensions[key] = str(value).lower() if isinstance(value, bool) else str(value)
        dimension_value = ",".join(f"{key}={resolved_dimensions[key]}" for key in sorted(resolved_dimensions))
        attributes = {
            "Metric": metric,
            "Dimensions": dimension_value,
        }
        for key, attribute in (("statistic", "Statistic"), ("comparison_operator", "ComparisonOperator")):
            item = required_assignment(values, key, resource["name"])
            attributes[attribute] = literal_string(raw_assignment(resource["source"], item), f"{key} for {resource['name']}")
        for key, attribute in (("period", "Period"), ("threshold", "Threshold"), ("evaluation_periods", "EvaluationPeriods")):
            item = required_assignment(values, key, resource["name"])
            parsed = parse_hcl_expression(raw_assignment(resource["source"], item), f"{key} for {resource['name']}")
            attributes[attribute] = number_string(parsed, f"{key} for {resource['name']}")
        actions = bool_attribute(resource["source"], values, "actions_enabled", f"actions_enabled for {resource['name']}", True)
        lifecycle_blocks = nested_blocks(resource, "lifecycle")
        ignored = False
        for block in lifecycle_blocks:
            if re.search(r"\bignore_changes\s*=\s*\[[^\]]*\bactions_enabled\b", block["text"], re.DOTALL):
                ignored = True
        if actions["line"] is None:
            actions["line"] = resource["line"]
            if ignored:
                actions["display"] = "true (default, ignore_changes)"
        resource["attributes"] = {
            "Metric": {
                "value": metric,
                "display": metric,
                "line": values["metric_name"]["line"],
            },
            "Dimensions": {
                "value": dimension_value,
                "display": dimension_value,
                "line": dimensions_assignment["line"],
            },
            "Statistic": {
                "value": attributes["Statistic"],
                "display": attributes["Statistic"],
                "line": values["statistic"]["line"],
            },
            "ComparisonOperator": {
                "value": attributes["ComparisonOperator"],
                "display": attributes["ComparisonOperator"],
                "line": values["comparison_operator"]["line"],
            },
            "Period": {
                "value": attributes["Period"],
                "display": attributes["Period"],
                "line": values["period"]["line"],
            },
            "Threshold": {
                "value": attributes["Threshold"],
                "display": attributes["Threshold"],
                "line": values["threshold"]["line"],
            },
            "EvaluationPeriods": {
                "value": attributes["EvaluationPeriods"],
                "display": attributes["EvaluationPeriods"],
                "line": values["evaluation_periods"]["line"],
            },
            "ActionsEnabled": actions,
        }
    return definitions


def short_endpoint(endpoint):
    return endpoint.rsplit(":", 1)[-1] if endpoint.startswith("arn:") else endpoint


def live_snapshot():
    fixture = os.environ.get("CW_DRIFT_LIVE_FILE")
    if fixture:
        try:
            data = json.loads(Path(fixture).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise DriftError(f"cannot read CW_DRIFT_LIVE_FILE: {error}") from error
        if not isinstance(data, dict):
            raise DriftError("CW_DRIFT_LIVE_FILE must contain an object")
        sectioned = any(key in SECTION_NAMES for key in data)
        if sectioned:
            if any(key not in SECTION_NAMES for key in data):
                raise DriftError("sectioned CW_DRIFT_LIVE_FILE has an unknown section")
            for key, value in data.items():
                if not isinstance(value, dict):
                    raise DriftError(f"CW_DRIFT_LIVE_FILE section {key} must be an object")
            for key in SECTION_NAMES:
                data.setdefault(key, {})
            checked = ["sqs", "sns", "dynamodb", "alarm"]
        else:
            if any(not isinstance(value, dict) for value in data.values()):
                raise DriftError("legacy CW_DRIFT_LIVE_FILE must map queue names to Attributes maps")
            data = {"sqs": data, "sns": {}, "dynamodb": {}, "alarms": {}}
            checked = ["sqs"]
        return validate_snapshot(data, checked)

    listing = run_aws(["sqs", "list-queues", "--queue-name-prefix", QUEUE_PREFIX, "--output", "json"])
    urls = listing.get("QueueUrls", [])
    if not isinstance(urls, list):
        raise DriftError("aws sqs list-queues returned an invalid QueueUrls value")
    queues = {}
    for url in urls:
        if not isinstance(url, str) or not url:
            raise DriftError("aws sqs list-queues returned an invalid queue URL")
        name = url.rstrip("/").rsplit("/", 1)[-1]
        if name.startswith(QUEUE_PREFIX):
            result = run_aws(["sqs", "get-queue-attributes", "--queue-url", url, "--attribute-names", "All", "--output", "json"])
            if not isinstance(result.get("Attributes"), dict):
                raise DriftError(f"aws sqs get-queue-attributes returned no Attributes for {name}")
            queues[name] = result["Attributes"]

    topics = {}
    topic_listing = run_aws(["sns", "list-topics", "--output", "json"])
    for item in topic_listing.get("Topics", []):
        arn = item.get("TopicArn") if isinstance(item, dict) else None
        if not isinstance(arn, str):
            raise DriftError("aws sns list-topics returned an invalid TopicArn")
        name = arn.rsplit(":", 1)[-1]
        if not name.startswith(CW_PREFIX):
            continue
        attrs = run_aws(["sns", "get-topic-attributes", "--topic-arn", arn, "--output", "json"]).get("Attributes")
        if not isinstance(attrs, dict):
            raise DriftError(f"aws sns get-topic-attributes returned no Attributes for {name}")
        listed = run_aws(["sns", "list-subscriptions-by-topic", "--topic-arn", arn, "--output", "json"]).get("Subscriptions", [])
        if not isinstance(listed, list):
            raise DriftError(f"aws sns list-subscriptions-by-topic returned invalid Subscriptions for {name}")
        subscriptions = []
        for subscription in listed:
            if not isinstance(subscription, dict):
                raise DriftError(f"invalid SNS subscription for {name}")
            subscription = dict(subscription)
            subscription_arn = subscription.get("SubscriptionArn")
            if isinstance(subscription_arn, str) and subscription_arn.startswith("arn:"):
                result = run_aws(["sns", "get-subscription-attributes", "--subscription-arn", subscription_arn, "--output", "json"])
                subscription["Attributes"] = result.get("Attributes", {})
            else:
                subscription["Attributes"] = {}
            subscriptions.append(subscription)
        topics[name] = {"Attributes": attrs, "Subscriptions": subscriptions}

    tables = {}
    table_listing = run_aws(["dynamodb", "list-tables", "--output", "json"])
    for name in table_listing.get("TableNames", []):
        if not isinstance(name, str):
            raise DriftError("aws dynamodb list-tables returned an invalid table name")
        if name.startswith(CW_PREFIX):
            tables[name] = {
                "Table": run_aws(["dynamodb", "describe-table", "--table-name", name, "--output", "json"]).get("Table", {}),
                "TimeToLiveDescription": run_aws(["dynamodb", "describe-time-to-live", "--table-name", name, "--output", "json"]).get("TimeToLiveDescription", {}),
                "ContinuousBackupsDescription": run_aws(["dynamodb", "describe-continuous-backups", "--table-name", name, "--output", "json"]).get("ContinuousBackupsDescription", {}),
            }

    alarm_result = run_aws(["cloudwatch", "describe-alarms", "--alarm-name-prefix", CW_PREFIX, "--alarm-types", "MetricAlarm", "--output", "json"])
    alarm_list = alarm_result.get("MetricAlarms", [])
    if not isinstance(alarm_list, list):
        raise DriftError("aws cloudwatch describe-alarms returned invalid MetricAlarms")
    alarms = {}
    for alarm in alarm_list:
        if not isinstance(alarm, dict) or not isinstance(alarm.get("AlarmName"), str):
            raise DriftError("aws cloudwatch describe-alarms returned an invalid alarm")
        alarms[alarm["AlarmName"]] = alarm
    return validate_snapshot(
        {"sqs": queues, "sns": topics, "dynamodb": tables, "alarms": alarms},
        ["sqs", "sns", "dynamodb", "alarm"],
    )


def validate_snapshot(data, checked):
    section_mapping = {"sqs": "sqs", "sns": "sns", "dynamodb": "dynamodb", "alarms": "alarms"}
    for section in section_mapping.values():
        if not isinstance(data.get(section), dict):
            raise DriftError(f"live {section} section must be an object")
    for name, value in data["sqs"].items():
        if not isinstance(value, dict):
            raise DriftError(f"live SQS attributes for {name} must be an object")
    for name, value in data["sns"].items():
        if not isinstance(value, dict) or not isinstance(value.get("Attributes", {}), dict) or not isinstance(value.get("Subscriptions", []), list):
            raise DriftError(f"live SNS topic for {name} has an invalid shape")
    for name, value in data["dynamodb"].items():
        if not isinstance(value, dict):
            raise DriftError(f"live DynamoDB table for {name} has an invalid shape")
    for name, value in data["alarms"].items():
        if not isinstance(value, dict):
            raise DriftError(f"live alarm for {name} must be an object")
    return {**data, "checked": checked}


def live_policy(attributes, key, description):
    raw = attributes.get(key)
    if raw in (None, ""):
        return "none"
    return canonical_json_value(raw, description)


def live_sns_subscriptions(topic, topic_name):
    result = []
    for subscription in topic.get("Subscriptions", []):
        if not isinstance(subscription, dict):
            raise DriftError(f"invalid live SNS subscription for {topic_name}")
        protocol = subscription.get("Protocol")
        endpoint = subscription.get("Endpoint")
        if not isinstance(protocol, str) or not isinstance(endpoint, str):
            raise DriftError(f"incomplete live SNS subscription for {topic_name}")
        result.append(f"{protocol}:{short_endpoint(endpoint)}")
    return sorted(result)


def live_subscription_match(topic, protocol, endpoint):
    for subscription in topic.get("Subscriptions", []):
        if (
            subscription.get("Protocol") == protocol
            and isinstance(subscription.get("Endpoint"), str)
            and short_endpoint(subscription["Endpoint"]) == short_endpoint(endpoint)
        ):
            return subscription
    return None


def live_key_schema(data, table_name):
    table = data.get("Table")
    if not isinstance(table, dict):
        raise DriftError(f"live DynamoDB Table missing for {table_name}")
    keys = table.get("KeySchema", [])
    definitions = table.get("AttributeDefinitions", [])
    if not isinstance(keys, list) or not isinstance(definitions, list):
        raise DriftError(f"invalid live DynamoDB key schema for {table_name}")
    types = {
        item.get("AttributeName"): item.get("AttributeType")
        for item in definitions if isinstance(item, dict)
    }
    selected = {}
    for item in keys:
        if not isinstance(item, dict) or item.get("KeyType") not in ("HASH", "RANGE"):
            raise DriftError(f"invalid live DynamoDB key in {table_name}")
        selected[item["KeyType"]] = item.get("AttributeName")
    if not isinstance(selected.get("HASH"), str) or selected["HASH"] not in types:
        raise DriftError(f"live DynamoDB HASH key has no type for {table_name}")
    value = f"HASH={selected['HASH']}:{types[selected['HASH']]}"
    if "RANGE" in selected:
        key = selected["RANGE"]
        if not isinstance(key, str) or key not in types:
            raise DriftError(f"live DynamoDB RANGE key has no type for {table_name}")
        value += f",RANGE={key}:{types[key]}"
    return value


def live_alarm_values(alarm, name):
    metric_name = alarm.get("MetricName")
    namespace = alarm.get("Namespace")
    if not isinstance(metric_name, str) or not isinstance(namespace, str):
        raise DriftError(f"live alarm {name} has no metric")
    dimensions = alarm.get("Dimensions", [])
    if not isinstance(dimensions, list):
        raise DriftError(f"live alarm dimensions are invalid for {name}")
    rendered_dimensions = []
    for dimension in dimensions:
        if not isinstance(dimension, dict) or not isinstance(dimension.get("Name"), str) or "Value" not in dimension:
            raise DriftError(f"invalid live alarm dimension for {name}")
        rendered_dimensions.append(f"{dimension['Name']}={dimension['Value']}")
    actions_enabled = alarm.get("ActionsEnabled")
    if not isinstance(actions_enabled, bool):
        raise DriftError(f"live alarm ActionsEnabled is invalid for {name}")
    required = {
        "Statistic": alarm.get("Statistic"),
        "ComparisonOperator": alarm.get("ComparisonOperator"),
    }
    for key, value in required.items():
        if not isinstance(value, str):
            raise DriftError(f"live alarm {key} is invalid for {name}")
    return {
        "Metric": f"{namespace}/{metric_name}",
        "Dimensions": ",".join(sorted(rendered_dimensions)),
        "Statistic": alarm["Statistic"],
        "ComparisonOperator": alarm["ComparisonOperator"],
        "Period": number_string(alarm.get("Period"), f"live Period for {name}"),
        "Threshold": number_string(alarm.get("Threshold"), f"live Threshold for {name}"),
        "EvaluationPeriods": number_string(alarm.get("EvaluationPeriods"), f"live EvaluationPeriods for {name}"),
        "ActionsEnabled": str(actions_enabled).lower(),
    }


def new_rows(definitions, live, checked):
    rows = []

    def add_row(kind, resource, attribute, actual, expected, root_name, path_line, status):
        rows.append({
            "kind": kind,
            "resource": f"{kind}:{resource}",
            "attribute": attribute,
            "live": actual,
            "git": expected,
            "root": root_name,
            "file_line": path_line,
            "status": status,
        })

    queue_defs = terraform_queues(Path(os.environ["CW_DRIFT_ROOT"]))
    queue_names = {
        "cloud-worker": [item for item in queue_defs if item["root"] == "cloud-worker"],
        "main": [item for item in queue_defs if item["root"] == "main"],
    }
    sqs_git = {item["name"]: item for item in queue_defs}
    if any(kind in checked for kind in ("sns", "dynamodb", "alarm")):
        definitions.update(terraform_cloud_resources(Path(os.environ["CW_DRIFT_ROOT"]), queue_names))

    for queue in queue_defs:
        name = queue["name"]
        if name not in live["sqs"]:
            name_line = queue["values"]["name"]["line"]
            add_row("sqs", name, "-", "-", "-", queue["root"], f"{queue['path']}:{name_line}", "MISSING")
            continue
        actual_values = live_values(live["sqs"][name], name)
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
            add_row(
                "sqs", name, attribute, actual, git_attribute["display"], queue["root"],
                f"{queue['path']}:{git_attribute['line']}",
                "ok" if actual == git_attribute["value"] else "DRIFT",
            )
    for name in live["sqs"]:
        if name not in sqs_git and name.startswith(QUEUE_PREFIX):
            add_row("sqs", name, "-", "-", "-", "none", "-", "UNOWNED")

    if "sns" in checked:
        sns_git = {item["name"]: item for item in definitions["sns"]}
        for topic in definitions["sns"]:
            name = topic["name"]
            if name not in live["sns"]:
                add_row("sns", name, "-", "-", "-", "cloud-worker", f"{topic['path']}:{topic['line']}", "MISSING")
                continue
            topic_live = live["sns"][name]
            live_attrs = topic_live.get("Attributes", {})
            actual_values = {
                "DeliveryPolicy": live_policy(live_attrs, "DeliveryPolicy", f"DeliveryPolicy for {name}"),
                "Subscriptions": ",".join(live_sns_subscriptions(topic_live, name)) or "none",
            }
            for attribute in KIND_ATTRIBUTES["sns"]:
                expected = topic["attributes"][attribute]
                actual = actual_values[attribute]
                add_row("sns", name, attribute, actual, expected["display"], "cloud-worker", f"{topic['path']}:{expected['line']}", "ok" if actual == expected["value"] else "DRIFT")

        for subscription in definitions["sns-sub"]:
            topic = live["sns"].get(subscription["topic_name"])
            match = live_subscription_match(topic, subscription["protocol"], subscription["endpoint"]) if topic else None
            name = subscription["name"]
            if match is None:
                add_row("sns-sub", name, "-", "-", "-", "cloud-worker", f"{subscription['path']}:{subscription['line']}", "MISSING")
                continue
            attrs = match.get("Attributes", {})
            if not isinstance(attrs, dict):
                raise DriftError(f"live SNS subscription Attributes are invalid for {name}")
            actual_values = {
                "RawMessageDelivery": str(bool_value(attrs.get("RawMessageDelivery", "false"), f"RawMessageDelivery for {name}")).lower(),
                "FilterPolicy": live_policy(attrs, "FilterPolicy", f"FilterPolicy for {name}"),
                "DeliveryPolicy": live_policy(attrs, "DeliveryPolicy", f"DeliveryPolicy for {name}"),
            }
            for attribute in KIND_ATTRIBUTES["sns-sub"]:
                expected = subscription["attributes"][attribute]
                actual = actual_values[attribute]
                add_row("sns-sub", name, attribute, actual, expected["display"], "cloud-worker", f"{subscription['path']}:{expected['line']}", "ok" if actual == expected["value"] else "DRIFT")
        for name in live["sns"]:
            if name.startswith(CW_PREFIX) and name not in sns_git:
                add_row("sns", name, "-", "-", "-", "none", "-", "UNOWNED")

    if "dynamodb" in checked:
        dynamodb_git = {item["name"]: item for item in definitions["dynamodb"]}
        for table in definitions["dynamodb"]:
            name = table["name"]
            if name not in live["dynamodb"]:
                add_row("dynamodb", name, "-", "-", "-", "cloud-worker", f"{table['path']}:{table['line']}", "MISSING")
                continue
            actual = live["dynamodb"][name]
            table_details = actual.get("Table", {})
            if not isinstance(table_details, dict):
                raise DriftError(f"live DynamoDB Table is invalid for {name}")
            billing_summary = table_details.get("BillingModeSummary", {})
            if not isinstance(billing_summary, dict):
                raise DriftError(f"live DynamoDB BillingModeSummary is invalid for {name}")
            billing_mode = billing_summary.get("BillingMode", "PROVISIONED")
            ttl = actual.get("TimeToLiveDescription", {})
            if not isinstance(ttl, dict):
                raise DriftError(f"live DynamoDB TimeToLiveDescription is invalid for {name}")
            ttl_status = ttl.get("TimeToLiveStatus")
            ttl_value = f"enabled ({ttl.get('AttributeName')})" if ttl_status in ("ENABLED", "ENABLING") else "disabled"
            backups = actual.get("ContinuousBackupsDescription", {})
            if not isinstance(backups, dict):
                raise DriftError(f"live DynamoDB ContinuousBackupsDescription is invalid for {name}")
            pitr = backups.get("PointInTimeRecoveryDescription", {})
            if not isinstance(pitr, dict):
                raise DriftError(f"live DynamoDB PointInTimeRecoveryDescription is invalid for {name}")
            pitr_value = "enabled" if pitr.get("PointInTimeRecoveryStatus") == "ENABLED" else "disabled"
            actual_values = {
                "BillingMode": billing_mode,
                "KeySchema": live_key_schema(actual, name),
                "TTL": ttl_value,
                "PointInTimeRecovery": pitr_value,
            }
            for attribute in KIND_ATTRIBUTES["dynamodb"]:
                expected = table["attributes"][attribute]
                value = actual_values[attribute]
                add_row("dynamodb", name, attribute, value, expected["display"], "cloud-worker", f"{table['path']}:{expected['line']}", "ok" if value == expected["value"] else "DRIFT")
        for name in live["dynamodb"]:
            if name.startswith(CW_PREFIX) and name not in dynamodb_git:
                add_row("dynamodb", name, "-", "-", "-", "none", "-", "UNOWNED")

    if "alarm" in checked:
        alarm_git = {item["name"]: item for item in definitions["alarm"]}
        for alarm in definitions["alarm"]:
            name = alarm["name"]
            if name not in live["alarms"]:
                add_row("alarm", name, "-", "-", "-", "cloud-worker", f"{alarm['path']}:{alarm['line']}", "MISSING")
                continue
            actual_values = live_alarm_values(live["alarms"][name], name)
            for attribute in KIND_ATTRIBUTES["alarm"]:
                expected = alarm["attributes"][attribute]
                actual = actual_values[attribute]
                add_row("alarm", name, attribute, actual, expected["display"], "cloud-worker", f"{alarm['path']}:{expected['line']}", "ok" if actual == expected["value"] else "DRIFT")
        for name in live["alarms"]:
            if name.startswith(CW_PREFIX) and name not in alarm_git:
                add_row("alarm", name, "-", "-", "-", "none", "-", "UNOWNED")

    root_order = {"cloud-worker": 0, "main": 1, "none": 2}
    rows.sort(key=lambda row: (
        root_order[row["root"]],
        KIND_ORDER[row["kind"]],
        row["resource"].split(":", 1)[1],
        KIND_ATTRIBUTES[row["kind"]].index(row["attribute"]) if row["attribute"] in KIND_ATTRIBUTES[row["kind"]] else -1,
    ))
    return rows


def main():
    root = Path(os.environ["CW_DRIFT_ROOT"])
    live = live_snapshot()
    rows = new_rows({"sns": [], "sns-sub": [], "dynamodb": [], "alarm": []}, live, live["checked"])
    drift_rows = [row for row in rows if row["status"] == "DRIFT"]
    missing = sum(row["status"] == "MISSING" for row in rows)
    unowned = sorted(row["resource"].split(":", 1)[1] for row in rows if row["status"] == "UNOWNED")
    summary = {
        "drift_attributes": len(drift_rows),
        "drift_resources": len({row["resource"] for row in drift_rows}),
        "missing": missing,
        "unowned": unowned,
        "checked": live["checked"],
    }

    if os.environ.get("CW_DRIFT_JSON") == "1":
        print(json.dumps({"rows": rows, "summary": summary}, separators=(",", ":")))
        return 1 if drift_rows or missing else 0

    print("\t".join(["RESOURCE", "ATTRIBUTE", "LIVE", "GIT", "ROOT", "FILE:LINE", "STATUS"]))
    for row in rows:
        print(
            "\t".join(
                [
                    row["resource"],
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
        f"{summary['drift_resources']} resource(s); missing: {summary['missing']}; "
        f"unowned: {len(unowned)} ({names}); checked: {','.join(live['checked'])}"
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
