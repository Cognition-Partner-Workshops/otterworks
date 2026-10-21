# fx-report deploy

## Sign-in

On report-01, Apache's `mod_authnz_ldap` asked for a directory login, allowed only the LDAP group
`cn=fx-desk,ou=groups,dc=bank,dc=internal` and passed the login to the CGI as `REMOTE_USER`
(`vm/fx-report.conf`). The service does not do sign-in itself. Sign-in happens at the shared ingress-nginx through external auth:

- `deploy/values.yaml` sets `ingress.annotations`:
  - `nginx.ingress.kubernetes.io/auth-url`: the platform oauth2-proxy's `/oauth2/auth?allowed_groups=fx-desk`. Without a session it answers 401, and nginx then redirects to `auth-signin`. A signed-in user outside the group gets 403.
  - `nginx.ingress.kubernetes.io/auth-signin`: `https://$host/oauth2/start?rd=$escaped_request_uri`.
  - `nginx.ingress.kubernetes.io/auth-response-headers: X-Auth-Request-User`: nginx copies the header from the auth response into the request it sends to the pod (`proxy_set_header`). Any value the client sent is replaced.
- `app/server.py` takes the user line from `X-Auth-Request-User`. When the header is missing or empty the page shows `unknown`, as the CGI did when `REMOTE_USER` was not set. The service ignores every other identity header.
- `/health` is called by the kubelet probes and by the pipeline's kind smoke (`kubectl port-forward` to the Service). Neither goes through the ingress, so neither needs a sign-in. `values-ci.yaml` therefore has no auth annotations and the kind smoke runs without sign-in. The NetworkPolicy in `helm/app` admits only the `ingress-nginx` and `monitoring` namespaces and pods in the app's own namespace. As a result, the only way to reach the pod with a forged header is from inside its own namespace.

### Platform items (not part of this service)

- The **oauth2-proxy** deployment, its Service `oauth2-proxy.oauth2-proxy.svc.cluster.local` and its `/oauth2` route on the app host belong to the platform. So does the identity provider that connects it to the bank directory. The proxy must run with `--set-xauthrequest` so that it returns `X-Auth-Request-User`.
- **Group name.** oauth2-proxy splits `allowed_groups` on commas (`extractAllowedEntities` in `oauthproxy.go`). A DN such as `cn=fx-desk,ou=groups,dc=bank,dc=internal` would therefore become four unrelated groups, and every user would get 403. The annotation names the group `fx-desk`. The platform's directory connector must report `cn=fx-desk,ou=groups,dc=bank,dc=internal` in the groups claim as `fx-desk`, for example with a Dex LDAP connector whose `groupSearch` uses `baseDN: ou=groups,dc=bank,dc=internal` and `nameAttr: cn`. If the platform emits a different form, change the `allowed_groups` value.
- **Chart support.** `helm/app` at `c56cbe8f6f4c` has no `ingress.annotations` value. Its Ingress template writes only `cert-manager.io/cluster-issuer`, and `helm template` silently drops `ingress.annotations`. The chart has no `values.schema.json` to reject it. The pipeline offers no other way to add them: `POST_RENDER` exists only in `policy-check.sh`, and `kind-verify.sh` and the EKS deploy run plain `helm`. Before go-live the platform chart needs an `ingress.annotations` map merged with the cert-manager annotation. Until then the block in `values.yaml` has no effect, and an Ingress rendered from this chart has **no sign-in**. Do not enable the ingress until the chart change is pinned.

### Check

- Unit tests: `cd app && UV_PYTHON=3.12 uv run --no-project --with pytest==8.3.5 pytest -v -k User`.
- Through a real ingress-nginx: `tests/ingress-auth/run.sh`. It needs a kind cluster with ingress-nginx and uses a stub oauth2-proxy. Output is in `tests/ingress-auth/evidence.txt`.
