# Edge namespaces (the shared ingress-nginx controller, monitoring) are enrolled
# in the mesh so that what they send *into* the app namespaces is mTLS, but they
# also receive traffic from outside the mesh: the NLB forwards client TCP to the
# ingress controller, and the monitoring stack is reached through its own
# Ingress. PERMISSIVE lets those pods keep accepting plaintext from off-mesh
# sources while STRICT (peer-authentication.yaml) still governs the app pods.
# Rendered by ensure_service_mesh with NAMESPACE substituted.
apiVersion: security.istio.io/v1
kind: PeerAuthentication
metadata:
  name: default
  namespace: ${NAMESPACE}
spec:
  mtls:
    mode: PERMISSIVE
