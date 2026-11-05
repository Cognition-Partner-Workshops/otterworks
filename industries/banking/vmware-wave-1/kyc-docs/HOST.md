# kyc-docs on kyc-01

Takes identity documents (passport, ID card, proof of address, payslip) from the onboarding flow and keeps them per customer for the compliance team.

- OS: RHEL 8, OpenJDK 11, Spring Boot 2.3 fat JAR at `/opt/kyc/kyc-docs.jar`, started by systemd (`vm/kyc-docs.service`) as user `kyc`.
- TLS: the app serves HTTPS itself on 8443 with a self-signed certificate from `/etc/kyc/keystore.p12`, made with keytool when the box was built. The keystore password is in `/etc/kyc/kyc.env`.
- Uploads: written to `/var/kyc/uploads/<customer>/`, backed up by the nightly VM snapshot.
- Logs: `/var/log/kyc/kyc-docs.log`.
- Monitoring: Actuator exposes only `/actuator/health` and `/actuator/prometheus` on HTTP management port 8081, bound to `172.30.250.10` by `MANAGEMENT_SERVER_ADDRESS` in the stand-in. Prometheus job `kyc-docs` scrapes `http://kyc-01:8081/actuator/prometheus` on the dedicated internal `kyc-monitoring` network. Port 8081 is not published and does not listen on the wave1 default network; HTTPS 8443 no longer serves Actuator. Outside Compose the management address defaults to loopback. Upload latency uses `http_server_requests_seconds_bucket` with `application="kyc-docs"`, `method="POST"`, `uri="/documents/{customer}"`. See `docs/runbooks/kyc-upload-latency.md` for network bootstrap and alert routing setup.
- API: `POST /documents/<customer>?kind=<kind>` (multipart `file`), `GET /documents/<customer>`.

In the wave stand-in, `make vm-up` serves it on https://localhost:8085/ (accept the certificate).

Plain `docker compose -f docker-compose.infra.yml up -d` at the repo root creates and owns the shared monitoring network without a pre-step. `make vm-up` here bootstraps it with infra's Compose labels when wave1 starts first. For direct wave1 Compose commands before infra starts, first run `bash scripts/ensure-kyc-monitoring-network.sh` from the repo root. The network uses `172.30.250.0/24`; reserve that subnet. It has no IPv4 bridge gateway on the host (`inhibit_ipv4=true`). Stop wave1 before infra teardown so infra can remove the network; remove any leftover with `docker network rm kyc-monitoring` after both stacks are down.
