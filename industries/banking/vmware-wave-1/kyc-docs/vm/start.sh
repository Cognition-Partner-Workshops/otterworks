#!/bin/sh
# Stand-in only: make a synthetic keystore with a random password on first
# start, keep the password in /etc/kyc/kyc.env like the VM, and hand it to
# the app through KEYSTORE_PASSWORD.
set -eu
umask 077
if [ ! -s /etc/kyc/kyc.env ] || [ ! -s /etc/kyc/keystore.p12 ]; then
  rm -f /etc/kyc/keystore.p12
  printf 'KEYSTORE_PASSWORD=%s\n' "$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')" > /etc/kyc/kyc.env
fi
. /etc/kyc/kyc.env
export KEYSTORE_PASSWORD
if [ ! -s /etc/kyc/keystore.p12 ]; then
  keytool -genkeypair -alias kyc -keyalg RSA -keysize 2048 -validity 3650 -dname "CN=kyc-01" \
    -storetype PKCS12 -keystore /etc/kyc/keystore.p12 -storepass:env KEYSTORE_PASSWORD -keypass:env KEYSTORE_PASSWORD
fi
exec java -Xmx512m -jar /opt/kyc/kyc-docs.jar
