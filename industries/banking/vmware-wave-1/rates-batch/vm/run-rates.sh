#!/bin/sh
# /opt/rates/bin/run-rates.sh, called from root's crontab on rates-01.
# fx-report on report-01 picks up /var/spool/rates/out over the NFS export.
JAVA_HOME=/usr/lib/jvm/java-11
cd /opt/rates || exit 1
exec "$JAVA_HOME/bin/java" -Xmx256m -jar /opt/rates/lib/rates-batch.jar \
  /var/spool/rates/in /var/spool/rates/out "$@" >> /var/log/rates/rates.log 2>&1
