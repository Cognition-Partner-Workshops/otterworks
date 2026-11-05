# kyc-docs on kyc-01

Takes identity documents (passport, ID card, proof of address, payslip) from the onboarding flow and keeps them per customer for the compliance team.

- OS: RHEL 8, OpenJDK 11, Spring Boot 2.3 fat JAR at `/opt/kyc/kyc-docs.jar`, started by systemd (`vm/kyc-docs.service`) as user `kyc`.
- TLS: the app serves HTTPS itself on 8443 with a self-signed certificate from `/etc/kyc/keystore.p12`, made with keytool when the box was built. The keystore password is in `/etc/kyc/kyc.env`.
- Uploads: written to `/var/kyc/uploads/<customer>/`, backed up by the nightly VM snapshot.
- Logs: `/var/log/kyc/kyc-docs.log`.
- Monitoring: the load balancer checks that TCP 8443 accepts a connection. There is no status page.
- API: `POST /documents/<customer>?kind=<kind>` (multipart `file`), `GET /documents/<customer>`.

In the wave stand-in, `make vm-up` serves it on https://localhost:8085/ (accept the certificate).

Provision `JWT_SECRET` in the service environment from the trusted token issuer. Tokens must be signed, expiring access tokens: uploads require subject `onboarding-service` and role `SERVICE`; listing requires `COMPLIANCE` or `ADMIN`. Missing or invalid credentials return 401, and other authenticated identities return 403. No shared default credential is provided.
