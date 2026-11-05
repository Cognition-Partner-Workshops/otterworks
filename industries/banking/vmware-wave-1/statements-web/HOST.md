# statements-web on stmt-web-01 and stmt-web-02

statements-web serves the statement pages that retail customers open from online banking. It runs on two VMs behind the hardware load balancer, which pins each customer to one VM with a cookie.

- OS: RHEL 7, Tomcat 8.5 under `/opt/tomcat`, Oracle JRE 8 from `/usr/java/jre1.8.0_202`.
- Deploy: the WAR is copied by hand to `/opt/tomcat/webapps/statements.war`, then `systemctl restart tomcat`.
- Datasource: `jdbc/StatementsDB` in `/opt/tomcat/conf/context.xml` (copy in `vm/conf/context.xml`), pointing at `wave1-db`.
- Application settings: `/opt/app/conf/statements.properties` (copy in `vm/opt-app-conf/`).
- Logs: `/var/log/statements/statements.log`, rotated daily, collected by a nightly rsync to the log server.
- PostgreSQL JDBC driver dropped into `/opt/tomcat/lib`.
- Pages: `/statements/accounts` and `/statements/statement?account=<id>`.

Run the VM stand-in with `make vm-up` from the wave folder; it answers on http://localhost:8081/statements/accounts.

## Hardened stand-in

The host inventory above describes the legacy VMs, not a deployment change. The
proposed stand-in uses the approved digest-pinned Tomcat 9 / JRE 17 image and
UID/GID 10001. It keeps the `javax.servlet` WAR, JNDI datasource and application
settings paths. Application and Tomcat logs go to the container console instead
of `/var/log/statements`. The WAR is expanded at build time so serving pages does
not require a writable application directory.

Build and exercise only this app with an isolated synthetic PostgreSQL fixture:

```sh
unset BANK_W1_EKS
docker build --target test -f vm/Dockerfile .
docker build -t mod05-f875-statements-runtime:local -f vm/Dockerfile .
python3 vm/test_runtime.py --image mod05-f875-statements-runtime:local \
  --run-token mod05-f875-statements-runtime-check \
  --out "$HOME/mod05-f875-statements-runtime-check" --hardened
```

Run these commands from `statements-web`. The harness requires a local
`postgres:16` fixture image and creates only token-prefixed Docker resources,
then removes its containers (including anonymous volumes) and network. It binds
HTTP to loopback and mounts synthetic datasource/settings files, never the host
inventory's datasource credentials. The hardened run uses a read-only root,
drops capabilities and mounts only `/tmp`, Tomcat `temp` and `work` as writable.
Use a unique token for each concurrent run. `--out` retains runtime versions,
UID, HTTP status codes and successful response body hashes; omit `--hardened`
only to characterize an unchanged legacy image. HTTP error bodies are not hashed
because Tomcat renders version-specific error pages.

This change does not address application authorization, session ownership,
datasource credential handling or the existing Log4j/JDBC dependencies. Full
VM-versus-kind business-day parity and production deployment are not established
by these focused runtime checks.
