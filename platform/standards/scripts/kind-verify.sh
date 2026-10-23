#!/usr/bin/env bash
# Runtime verification on a throwaway kind cluster: Kyverno enforces the
# platform policies at admission, the chart is installed, and the smoke paths
# in deploy/platform.yaml are called. Pod logs and events always land in $OUT.
#   kind-verify.sh <app-dir> <image-repository> <image-tag>
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
app_dir="$1"; repo="$2"; tag="$3"
app="$(basename "$app_dir")"
OUT="${OUT:-/tmp/kind-verify/$app}"; mkdir -p "$OUT"
CLUSTER="${KIND_CLUSTER:-platform-verify}"
KYVERNO_CHART_VERSION="${KYVERNO_CHART_VERSION:-3.2.6}"
NS="app-$app"
result() { printf '{"app":"%s","stage":"%s","status":"%s","detail":"%s"}\n' "$app" "$1" "$2" "$3" > "$OUT/result.json"; }
collect() {
  kubectl get all,events -n "$NS" -o wide > "$OUT/resources.txt" 2>&1 || true
  kubectl describe pods -n "$NS" > "$OUT/describe-pods.txt" 2>&1 || true
  for p in $(kubectl get pods -n "$NS" -o name 2>/dev/null); do
    kubectl logs -n "$NS" "$p" --all-containers --tail=400 > "$OUT/logs-${p#pod/}.txt" 2>&1 || true
    kubectl logs -n "$NS" "$p" --all-containers --previous --tail=200 > "$OUT/logs-${p#pod/}-previous.txt" 2>/dev/null || true
  done
  kubectl get events -n "$NS" --sort-by=.lastTimestamp 2>/dev/null | tail -20
  for f in "$OUT"/logs-*.txt; do [[ -s "$f" ]] && { echo "--- $(basename "$f") (last 40 lines)"; tail -40 "$f"; }; done
}
trap collect EXIT

if ! kind get clusters 2>/dev/null | grep -qx "$CLUSTER"; then
  kind create cluster --name "$CLUSTER" --wait 120s || { result cluster fail "kind create failed"; exit 1; }
fi
if ! helm status kyverno -n kyverno >/dev/null 2>&1; then
  helm repo add kyverno https://kyverno.github.io/kyverno/ >/dev/null 2>&1
  helm install kyverno kyverno/kyverno -n kyverno --create-namespace --version "$KYVERNO_CHART_VERSION" \
    --set admissionController.replicas=1 --set backgroundController.enabled=false \
    --set cleanupController.enabled=false --set reportsController.enabled=false --wait --timeout 5m \
    || { result kyverno fail "kyverno install failed"; exit 1; }
fi
kubectl apply -f "$here/policy/kyverno/policies.yaml" >/dev/null
kubectl wait --for=condition=Ready clusterpolicy --all --timeout=120s >/dev/null

kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl label namespace "$NS" platform.otterworks.dev/policy=enforced --overwrite >/dev/null
if [[ -d "$app_dir/deploy/kind-deps" ]]; then
  kubectl create namespace deps --dry-run=client -o yaml | kubectl apply -f - >/dev/null
  kubectl apply -n deps -f "$app_dir/deploy/kind-deps" >/dev/null
  kubectl wait -n deps --for=condition=Available deployment --all --timeout=180s
fi
if [[ -f "$app_dir/deploy/kind-secrets.env" ]]; then
  for s in $(cut -d. -f1 < "$app_dir/deploy/kind-secrets.env" | sort -u); do
    grep "^$s\." "$app_dir/deploy/kind-secrets.env" | sed "s/^$s\.//" > "$OUT/.secret.env"
    kubectl create secret generic "$s" -n "$NS" --from-env-file="$OUT/.secret.env" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
    rm -f "$OUT/.secret.env"
  done
fi

kind load docker-image "$repo:$tag" --name "$CLUSTER" >/dev/null || { result load fail "image not loadable"; exit 1; }
values=(-f "$app_dir/deploy/values.yaml")
[[ -f "$app_dir/deploy/values-ci.yaml" ]] && values+=(-f "$app_dir/deploy/values-ci.yaml")
echo "== helm install $app into $NS (Kyverno enforcing)"
if ! helm upgrade --install "$app" "$here/helm/app" -n "$NS" "${values[@]}" \
      --set image.repository="$repo" --set image.tag="$tag" --wait --timeout 4m 2>&1 | tee "$OUT/helm.txt"; then
  result deploy fail "$(grep -o 'admission webhook.*' "$OUT/helm.txt" | head -1 | tr '"' "'" | cut -c1-300)"
  exit 1
fi

workload="$(python3 -c "import yaml,sys;print(yaml.safe_load(open('$app_dir/deploy/values.yaml')).get('workload','web'))")"
if [[ "$workload" == cronjob ]]; then
  kubectl create job -n "$NS" "$app-smoke" --from=cronjob/"$app" >/dev/null
  if kubectl wait -n "$NS" --for=condition=Complete job/"$app-smoke" --timeout=180s; then result smoke pass "job completed"; exit 0; fi
  result smoke fail "job did not complete"; exit 1
fi

kubectl port-forward -n "$NS" svc/"$app" 18080:80 > "$OUT/port-forward.txt" 2>&1 &
pf=$!; sleep 4
status=0
while IFS=' ' read -r path expect; do
  code="$(curl -s -o "$OUT/smoke-body.txt" -w '%{http_code}' "http://127.0.0.1:18080$path")"
  echo "smoke GET $path -> $code (want $expect)"
  [[ "$code" == "$expect" ]] || status=1
done < <(python3 -c "import yaml;[print(s['path'],s.get('expect',200)) for s in yaml.safe_load(open('$app_dir/deploy/platform.yaml')).get('smoke',[])]")
kill $pf 2>/dev/null
if [[ $status -eq 0 ]]; then result smoke pass "all smoke paths answered"; else result smoke fail "a smoke path returned the wrong status"; fi
exit $status
