#!/usr/bin/env bash
# Sign-in through a real ingress-nginx on kind: the chart from platform/standards at $STANDARDS_REF,
# deploy/values.yaml's auth annotations applied to the Ingress (helm/app does not render them yet, see
# deploy/README.md), a stub oauth2-proxy (stub_oauth2_proxy.py) and the golden rates files.
#   tests/ingress-auth/run.sh      (from the fx-report folder; needs docker, kind, kubectl, helm, python3)
# Uses the current kubectl context, which must have ingress-nginx installed (kind provider manifest).
set -euo pipefail
cd "$(dirname "$0")/../.."
STANDARDS_REF="${STANDARDS_REF:-c56cbe8f6f4c}"
CLUSTER="${KIND_CLUSTER:-fx-auth}"
IMAGE=fx-report-auth-check:local
NS=app-fx-report
std="$(mktemp -d)"; trap 'rm -rf "$std"; kill ${pf:-} 2>/dev/null || true' EXIT
(cd "$(git rev-parse --show-toplevel)" && git archive "$STANDARDS_REF" platform/standards/helm/app) | tar x -C "$std"

# Throwaway image (the service's Dockerfile is separate work): app/ plus the golden rates as RATES_DIR.
docker build -q -t "$IMAGE" -f - . >/dev/null <<'DOCKERFILE'
FROM python:3.12-slim
COPY app/server.py app/rates.py /srv/app/
COPY tests/golden/rates/ /mnt/rates-out/
USER 10001
ENV TZ=UTC
CMD ["python", "/srv/app/server.py"]
DOCKERFILE
for img in "$IMAGE" python:3.12-slim; do  # not `kind load`: it fails on single-platform saves of multi-arch images
  docker save --platform linux/amd64 "$img" | docker exec -i "$CLUSTER-control-plane" ctr -n k8s.io images import - >/dev/null
done

kubectl create namespace oauth2-proxy --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl -n oauth2-proxy create configmap stub --from-file=tests/ingress-auth/stub_oauth2_proxy.py \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl -n oauth2-proxy apply -f - >/dev/null <<'YAML'
apiVersion: apps/v1
kind: Deployment
metadata: {name: oauth2-proxy}
spec:
  selector: {matchLabels: {app: oauth2-proxy}}
  template:
    metadata: {labels: {app: oauth2-proxy}}
    spec:
      containers:
        - name: stub
          image: python:3.12-slim
          imagePullPolicy: Never
          command: [python, /stub/stub_oauth2_proxy.py]
          volumeMounts: [{name: stub, mountPath: /stub}]
      volumes: [{name: stub, configMap: {name: stub}}]
---
apiVersion: v1
kind: Service
metadata: {name: oauth2-proxy}
spec:
  selector: {app: oauth2-proxy}
  ports: [{port: 80, targetPort: 4180}]
YAML

kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
helm upgrade --install fx-report "$std/platform/standards/helm/app" -n "$NS" -f deploy/values.yaml \
  --set app=fx-report,owner=fx-desk,costCenter=treasury-ops \
  --set image.repository="${IMAGE%:*}",image.tag="${IMAGE#*:}",image.pullPolicy=Never \
  --set ingress.enabled=true,ingress.host=fx-report.test,ingress.tls=false --wait --timeout 3m >/dev/null
kubectl -n oauth2-proxy rollout status deploy/oauth2-proxy --timeout=120s >/dev/null

echo "== Ingress annotations rendered by helm/app@$STANDARDS_REF"
kubectl -n "$NS" get ingress fx-report -o jsonpath='{.metadata.annotations}'; echo
sed -n 's/^ *\(nginx\.ingress\.kubernetes\.io\/[a-z-]*\): "\(.*\)"$/\1=\2/p' deploy/values.yaml \
  | xargs -d '\n' kubectl -n "$NS" annotate ingress fx-report --overwrite >/dev/null
echo "== after applying deploy/values.yaml ingress.annotations by hand"
kubectl -n "$NS" get ingress fx-report -o jsonpath='{.metadata.annotations}'; echo
sleep 5  # controller reload

kubectl -n ingress-nginx port-forward svc/ingress-nginx-controller 18088:80 >/dev/null 2>&1 & pf=$!
sleep 3
fail=0
check() {  # name, want status, want body substring ("" = none), curl args...
  local name="$1" want="$2" grep="$3"; shift 3
  local out code
  out="$(curl -s -o /tmp/fx-auth-body -w '%{http_code} %{redirect_url}' -H 'Host: fx-report.test' "$@" \
    'http://127.0.0.1:18088/fx/fx-report.cgi?day=2026-10-15')"
  code="${out%% *}"
  local line; line="$(grep -o 'Business date[^<]*' /tmp/fx-auth-body || true)"
  if [[ "$code" == "$want" && ( -z "$grep" || "$line" == *"$grep"* ) ]]; then r=PASS; else r=FAIL; fail=1; fi
  printf '%-4s %-52s -> %s %s\n' "$r" "$name" "$out" "${line:+| $line}"
}
check "no session: redirected to sign-in" 302 ""
check "no session, spoofed X-Auth-Request-User" 302 "" -H 'X-Auth-Request-User: mallory'
check "session outside fx-desk: rejected" 403 "" -b '_oauth2_proxy=eve|traders'
check "fx-desk member: report with their user" 200 "user jdoe" -b '_oauth2_proxy=jdoe|fx-desk'
check "fx-desk member, spoofed header replaced" 200 "user jdoe" -b '_oauth2_proxy=jdoe|fx-desk' -H 'X-Auth-Request-User: mallory'
echo "== /health on the Service, as the kubelet probes and the kind smoke call it (no ingress, no sign-in)"
kubectl -n "$NS" run probe --rm -i --restart=Never --image=python:3.12-slim --image-pull-policy=Never -q -- \
  python -c 'import urllib.request as u; r=u.urlopen("http://fx-report/health"); print(r.status, r.read().decode().strip())'
exit $fail
