# kyc-docs on kyc-01

Takes identity documents (passport, ID card, proof of address, payslip) from the onboarding flow and keeps them per customer for the compliance team.

- OS: RHEL 8, OpenJDK 11, Spring Boot 2.3 fat JAR at `/opt/kyc/kyc-docs.jar`, started by systemd (`vm/kyc-docs.service`) as user `kyc`.
- TLS: the app serves HTTPS itself on 8443 with a self-signed certificate from `/etc/kyc/keystore.p12`, made with keytool when the box was built. The keystore password is in `/etc/kyc/kyc.env`.
- Uploads: written to `/var/kyc/uploads/<customer>/`, backed up by the nightly VM snapshot.
- Logs: `/var/log/kyc/kyc-docs.log`.
- Monitoring: Actuator exposes only `/actuator/health` and `/actuator/prometheus` on the existing HTTPS 8443 listener. Prometheus job `kyc-docs` scrapes `kyc-01:8443` on the VM stand-in network (join the Prometheus container to `wave1-vm_default`). The stand-in uses a self-signed certificate, so this scrape disables certificate verification; use a trusted certificate and verification outside the stand-in. No extra management port is published. Upload latency uses `http_server_requests_seconds_bucket` with `application="kyc-docs"`, `method="POST"`, `uri="/documents/{customer}"`. See `docs/runbooks/kyc-upload-latency.md` for alert routing setup.
- API: `POST /documents/<customer>?kind=<kind>` (multipart `file`), `GET /documents/<customer>`.

In the wave stand-in, `make vm-up` serves it on https://localhost:8085/ (accept the certificate).
