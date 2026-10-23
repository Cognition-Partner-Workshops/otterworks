# fx-report on report-01

The FX desk's morning report: closing rate, average mid, intraday range and day-on-day change for each currency pair, built from the rates-batch output.

- OS: RHEL 6, Apache 2.2, system Perl 5.10 with CGI.pm from the OS packages.
- Install: `/var/www/fx-report/cgi-bin/fx-report.cgi` and `lib/FxReport/Rates.pm`, copied by hand.
- Apache config: `/etc/httpd/conf.d/fx-report.conf` (copy in `vm/`). Sign-in is `mod_authnz_ldap` against the directory, restricted to the `fx-desk` group; `mod_expires` caches the page for an hour.
- Input: `/mnt/rates-out`, the NFS export of rates-01's `/var/spool/rates/out`.
- Pages: `/fx/fx-report.cgi?day=<yyyy-mm-dd>`.
- Users: about a dozen people on the desk, every weekday morning.

In the wave stand-in, `make vm-up` serves it on http://localhost:8086/fx/fx-report.cgi without the LDAP sign-in.
