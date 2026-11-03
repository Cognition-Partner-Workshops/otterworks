#!/bin/bash
# Builds the OW_BILLING Oracle estate exactly as `make oracle-billing-up` and
# `make oracle-billing-seed` do locally, but on 1521. Progress lands in
# /var/log/ow-oracle-billing.log; /var/tmp/ow-ready appears when it is done.
set -euxo pipefail
exec > >(tee -a /var/log/ow-oracle-billing.log) 2>&1

dnf install -y docker git make
systemctl enable --now docker
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
usermod -aG docker ec2-user
curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

git clone --depth 1 --branch "${repo_ref}" "${repo_url}" /opt/otterworks
cd /opt/otterworks

export ORACLE_BILLING_DB_PORT=1521
make oracle-billing-up
make oracle-billing-seed NS="${seed_ns}" SCALE="${seed_scale}"

RO_PASSWORD=$(aws ssm get-parameter --region "${region}" --with-decryption \
  --name "${ro_password_ps}" --query Parameter.Value --output text)
docker compose -f docker-compose.oracle-billing.yml -p otterworks-oracle-billing \
  exec -T oracle-billing sqlplus -s / as sysdba <<SQL
WHENEVER SQLERROR EXIT SQL.SQLCODE
ALTER SESSION SET CONTAINER = FREEPDB1;
CREATE USER ${ro_user} IDENTIFIED BY "$RO_PASSWORD";
GRANT CREATE SESSION, SELECT ANY DICTIONARY, SELECT ANY TABLE TO ${ro_user};
EXIT;
SQL

touch /var/tmp/ow-ready
