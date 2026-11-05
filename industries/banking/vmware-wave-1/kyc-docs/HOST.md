# kyc-docs on kyc-01

Takes identity documents (passport, ID card, proof of address, payslip) from the onboarding flow and keeps them per customer for the compliance team.

- OS: RHEL 8, OpenJDK 11, Spring Boot 2.3 fat JAR at `/opt/kyc/kyc-docs.jar`, started by systemd (`vm/kyc-docs.service`) as user `kyc`.
- TLS: the app serves HTTPS itself on 8443 with a self-signed certificate from `/etc/kyc/keystore.p12`, made with keytool when the box was built. The keystore password is in `/etc/kyc/kyc.env`.
- Uploads: written to `/var/kyc/uploads/<customer>/`, backed up by the nightly VM snapshot.
- Logs: `/var/log/kyc/kyc-docs.log`.
- Monitoring: the load balancer checks that TCP 8443 accepts a connection. There is no status page.
- API: HTTP Basic over HTTPS, stateless. `POST /documents/<customer>?kind=<kind>` (multipart `file`) requires the UPLOADER service principal; `GET /documents/<customer>` requires the REVIEWER service principal. Other routes are denied. These are service roles across customers, not customer identities.
- Configure `KYC_UPLOADER_USERNAME`, `KYC_UPLOADER_PASSWORD_HASH`, `KYC_REVIEWER_USERNAME`, and `KYC_REVIEWER_PASSWORD_HASH` with BCrypt hashes via the VM's `/etc/kyc/kyc.env` or mounted Spring configuration (`kyc.auth.uploader.username`, `kyc.auth.uploader.password-hash`, and the corresponding `reviewer` properties). No users exist unless both their username and hash are nonblank. The stand-in starts Java directly, so supply these variables explicitly through the container environment; it does not read the systemd environment file.

In the wave stand-in, `make vm-up` serves it on https://localhost:8085/ (accept the certificate).
