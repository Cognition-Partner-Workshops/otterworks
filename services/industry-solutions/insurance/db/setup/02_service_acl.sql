-- COMMISSION_PKG is now a thin delegate: its body calls the extracted rule
-- owner (commission-service) over HTTP. Oracle refuses outbound callouts
-- unless the calling schema holds a network ACE for the target host, so grant
-- COMMISSION_PAY exactly one: http to commission-service:8000, nothing else.
-- Run as SYSTEM against FREEPDB1. Idempotent: 00_init.sh runs it on every boot
-- so fixtures initialized before this file existed get the ACE too.
WHENEVER SQLERROR EXIT SQL.SQLCODE

DECLARE
    l_have PLS_INTEGER;
BEGIN
    SELECT COUNT(*) INTO l_have
      FROM dba_host_aces
     WHERE LOWER(host) = 'commission-service'
       AND lower_port = 8000 AND upper_port = 8000
       AND principal = 'COMMISSION_PAY' AND privilege = 'HTTP';
    IF l_have > 0 THEN
        RETURN;
    END IF;
    DBMS_NETWORK_ACL_ADMIN.append_host_ace(
        host       => 'commission-service',
        lower_port => 8000,
        upper_port => 8000,
        ace        => xs$ace_type(
                          privilege_list => xs$name_list('http'),
                          principal_name => 'COMMISSION_PAY',
                          principal_type => xs_acl.ptype_db));
END;
/

EXIT;
