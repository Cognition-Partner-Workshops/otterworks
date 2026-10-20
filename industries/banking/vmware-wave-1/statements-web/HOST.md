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
