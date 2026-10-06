#!/usr/bin/env bash
# Bootstrap for the legacy-portal "before" host: Amazon Corretto 11, a local
# PostgreSQL 15 with the three bounded-context schemas, the fat jar from the
# run's artifact bucket, a systemd unit, and the CloudWatch agent shipping the
# application log.
set -euxo pipefail
exec > >(tee /var/log/legacy-portal-bootstrap.log | logger -t lp-bootstrap) 2>&1

dnf install -y java-11-amazon-corretto postgresql15-server amazon-cloudwatch-agent

# --- PostgreSQL on the instance, deliberately not a managed database ---
if [ ! -s /var/lib/pgsql/data/PG_VERSION ]; then
  if command -v postgresql-setup >/dev/null; then
    postgresql-setup --initdb
  else
    install -d -o postgres -g postgres /var/lib/pgsql/data
    sudo -u postgres /usr/bin/initdb -D /var/lib/pgsql/data
  fi
fi
# The app authenticates with a password over TCP; make those rules win.
sed -i '1i host all legacyportal ::1/128 scram-sha-256' /var/lib/pgsql/data/pg_hba.conf
sed -i '1i host all legacyportal 127.0.0.1/32 scram-sha-256' /var/lib/pgsql/data/pg_hba.conf
systemctl enable --now postgresql
for i in $(seq 1 30); do
  /usr/bin/pg_isready -q && break
  sleep 2
done

DB_PASS="$(openssl rand -hex 12)"
sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
CREATE USER legacyportal WITH PASSWORD '$DB_PASS';
CREATE DATABASE legacyportal OWNER legacyportal;
SQL
sudo -u postgres psql -d legacyportal -v ON_ERROR_STOP=1 <<'SQL'
CREATE SCHEMA IF NOT EXISTS announcements AUTHORIZATION legacyportal;
CREATE SCHEMA IF NOT EXISTS user_preferences AUTHORIZATION legacyportal;
CREATE SCHEMA IF NOT EXISTS feedback AUTHORIZATION legacyportal;
SQL

# --- Application jar from the run's artifact bucket ---
useradd -r -s /usr/sbin/nologin legacyportal || true
install -d -o legacyportal -g legacyportal /opt/legacy-portal /var/log/legacy-portal
aws s3 cp "s3://${artifact_bucket}/${jar_key}" /opt/legacy-portal/legacy-portal.jar --region "${region}"
echo "${jar_md5}  /opt/legacy-portal/legacy-portal.jar" | md5sum -c -
chown legacyportal:legacyportal /opt/legacy-portal/legacy-portal.jar

cat >/etc/legacy-portal.env <<EOF
SPRING_PROFILES_ACTIVE=postgres
SPRING_DATASOURCE_URL=jdbc:postgresql://127.0.0.1:5432/legacyportal
SPRING_DATASOURCE_USERNAME=legacyportal
SPRING_DATASOURCE_PASSWORD=$DB_PASS
LOGGING_FILE_NAME=/var/log/legacy-portal/app.log
EOF
chmod 640 /etc/legacy-portal.env
chown root:legacyportal /etc/legacy-portal.env

JAVA_BIN="$(readlink -f "$(command -v java)")"
cat >/etc/systemd/system/legacy-portal.service <<EOF
[Unit]
Description=OtterWorks Legacy Portal (modular monolith)
After=network.target postgresql.service

[Service]
Type=simple
User=legacyportal
WorkingDirectory=/opt/legacy-portal
EnvironmentFile=/etc/legacy-portal.env
ExecStart=$JAVA_BIN -jar /opt/legacy-portal/legacy-portal.jar
SuccessExitStatus=143
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now legacy-portal

# --- CloudWatch agent: ship the application log ---
cat >/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json <<EOF
{
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/legacy-portal/app.log",
            "log_group_name": "${log_group_name}",
            "log_stream_name": "{instance_id}",
            "timestamp_format": "%Y-%m-%d %H:%M:%S.%f"
          }
        ]
      }
    }
  }
}
EOF
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config -m ec2 -s \
  -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json

echo "legacy-portal bootstrap complete"
