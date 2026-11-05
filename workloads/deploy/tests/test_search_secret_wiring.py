import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def function(path, name):
    source = (ROOT / path).read_text()
    return re.search(rf"^{name}\(\) \{{.*?^\}}", source, re.M | re.S).group(0)


@pytest.mark.parametrize("path", ["scripts/deploy-dev.sh", "scripts/lib/tenant-common.sh"])
def test_search_receives_gateway_jwt_secret_and_requires_auth(path):
    script = """
set -euo pipefail
declare -A CONTAINER_PORT=([search-service]=8087)
JWT_SECRET=test-shared-jwt-secret
JVM_SERVICES=''
AWS_REGION=test-region
T_WIRE_EVENTING=false
REDIS_HOST=redis
T_REDIS_HOST=redis
MEILISEARCH_URL=http://meili:7700
T_MEILI_URL=http://meili:7700
SNOWFLAKE_ENABLED=false
irsa_arn() { :; }
add_secret() { SECRET_KV+=("$1" "$2"); }
""" + function(path, "build_helm_args") + """
build_helm_args search-service
printf '%s\n' "${SECRET_KV[@]}" "${EXTRA_ARGS[@]}"
"""
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True)
    lines = result.stdout.splitlines()
    assert lines[:2] == ["JWT_SECRET", "test-shared-jwt-secret"]
    assert "config.REQUIRE_AUTH=true" in lines


@pytest.mark.parametrize("state,expected", [
    ("missing-namespace", []),
    ("missing-peer-key", []),
    ("missing-search", ["api-gateway"]),
    ("unconfigured", ["api-gateway", "search-service"]),
    ("gateway-configured", ["search-service"]),
    ("configured", []),
])
def test_peer_trust_updates_both_jwt_verifiers(state, expected):
    script = """
set -euo pipefail
DRY_RUN=0
REPO_ROOT=/test-repo
demo_namespace() { printf '%s' "$1"; }
token_run() { printf 'run'; }
dlog() { :; }
dwarn() { :; }
kubectl() {
  if [[ "$*" == *'get secret'* ]]; then
    if [[ "$STATE" == missing-namespace ]]; then return 1; fi
    if [[ "$STATE" == missing-search && "$*" == *search-service-secrets* ]]; then return 1; fi
    if [[ "$*" == *JWT_PEER_SECRET* ]]; then
      if [[ "$STATE" == configured || ( "$STATE" == gateway-configured && "$*" == *api-gateway-secrets* ) ]]; then
        printf 'test-peer-key' | base64
      fi
    elif [[ "$*" == *JWT_SECRET* && "$STATE" != missing-peer-key ]]; then
      printf 'test-peer-key' | base64
    fi
  fi
  return 0
}
helm() { printf '%s\n' "$4" >&2; }
""" + function("scripts/lib/demo-common.sh", "trust_peer_tokens") + "\ntrust_peer_tokens run-after\n"
    result = subprocess.run(["bash", "-c", f"STATE={state}\n" + script], capture_output=True, text=True, check=True)
    assert result.stderr.splitlines() == expected
