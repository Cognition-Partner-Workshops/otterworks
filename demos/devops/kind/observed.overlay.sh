#!/usr/bin/env bash
metrics_version=v0.8.1
metrics_image="registry.k8s.io/metrics-server/metrics-server:$metrics_version"
docker pull "$metrics_image"
kind load docker-image "$metrics_image" --name "$cluster"
kubectl --context "$context" apply -f "https://github.com/kubernetes-sigs/metrics-server/releases/download/$metrics_version/components.yaml"
kubectl --context "$context" --namespace kube-system patch deployment metrics-server --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
kubectl --context "$context" --namespace kube-system rollout status deployment/metrics-server --timeout=120s

revision=$(git -C "$ROOT" log -1 --format=%H -- "$DEMO/values/api-gateway-observed.yaml")
render_or_install upgrade api-gateway --kube-context "$context" --description "git $revision" \
  -f "$DEMO/values/api-gateway-observed.yaml"
kubectl --context "$context" --namespace "$NAMESPACE" patch deployment collab-service --type=strategic \
  -p '{"metadata":{"labels":{"owner":null}},"spec":{"template":{"metadata":{"labels":{"owner":null}},"spec":{"containers":[{"name":"collab-service","resources":{"requests":{"cpu":"320m"}}}]}}}}'
kubectl --context "$context" --namespace "$NAMESPACE" rollout status deployment/collab-service --timeout=90s
