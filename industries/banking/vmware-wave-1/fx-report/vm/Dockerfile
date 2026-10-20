# Stand-in for report-01: Apache with mod_cgi and the system Perl, rates
# spool mounted where the NFS export lands. LDAP auth is left out of the
# stand-in; the real config is in vm/fx-report.conf.
FROM docker.io/library/httpd:2.4
RUN apt-get update && apt-get install -y --no-install-recommends perl libcgi-pm-perl && rm -rf /var/lib/apt/lists/* \
 && sed -i -E 's/^[[:space:]]*#[[:space:]]*(LoadModule cgid?_module)/\1/' /usr/local/apache2/conf/httpd.conf \
 && printf 'ScriptAlias /fx/ /var/www/fx-report/cgi-bin/\n<Directory "/var/www/fx-report/cgi-bin">\n Options +ExecCGI\n Require all granted\n</Directory>\nPassEnv TZ\n' >> /usr/local/apache2/conf/httpd.conf \
 && mkdir -p /mnt/rates-out
COPY lib /var/www/fx-report/lib
COPY cgi-bin /var/www/fx-report/cgi-bin
