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

## Statements access-control integration

Both pages now require a container-authenticated `HttpServletRequest.getUserPrincipal()`.
No request header, query parameter or session attribute is accepted as identity. This WAR
does not implement a login form or validate SSO tokens. The owner must configure the
container's online-banking authenticator/realm (and its route constraints) to establish
the principal before the servlet runs. A raw reverse-proxy identity header is not sufficient.
The supplied VM stand-in has no authenticator and deliberately returns **401** for these
pages until one is integrated; the VM smoke check now asserts anonymous **401**, not 200.

The database schema has no customer identity relationship. Until the owner supplies an
authoritative mapping, the application denies access rather than deriving ownership from
holder names or caller-supplied account IDs. Set `STATEMENTS_ACCESS_FILE` to the absolute
path of a read-only, operator-managed UTF-8 Java properties file outside the WAR. Each key
is an exact authenticated principal name; its value is a comma-separated list of owned
account IDs. For example, **synthetic test configuration only**:

```properties
synthetic-a=TEST0001
synthetic-b=TEST0002
synthetic-joint=TEST0001,TEST0002
```

Do not ship these sample identities as a production mapping. Only trusted operators may
write the mapping; customers must not be able to edit or upload it. Keys with Java
properties special characters must be escaped. The file is loaded at servlet initialization:
update it atomically and reload the WAR for grants/revocations to take effect on both VMs.
No path or an empty file grants nobody; a missing/unreadable configured file or malformed
grant fails servlet initialization. Authentication without a mapping returns **403**.

Accounts queries bind only mapped account IDs. Requests for another account or an unmapped
nonexistent account both return **404**, before statement queries, logging or session updates.
Malformed account IDs still return **400** for mapped authenticated callers. A last-viewed
link is displayed only if it is in the current caller's returned account set. Responses use
`Cache-Control: no-store`. Successful owned statement formatting, ordering, page size and
last-viewed navigation are unchanged.

Run `mvn test` for servlet/DAO regression checks using synthetic in-memory H2 data.
These tests exercise the principal integration boundary, not real SSO or production
entitlements. Container authentication, principal namespace consistency, authoritative
ownership provisioning/revocation and actual load-balancer exposure require owner validation.
