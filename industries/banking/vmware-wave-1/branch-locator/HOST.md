# branch-locator on web-02

The "find a branch" page on the public site. Takes a postcode or district, asks the internal geocoder for coordinates, and lists the three nearest branches with whether they are open now.

- OS: CentOS 7, system Python 2.7, packages from `requirements.txt` installed globally with pip.
- Install: `/opt/branch-locator/app`, started by systemd (`vm/branch-locator.service`) as the unprivileged `branch-locator` user, served by waitress (`app/server.py`) rather than Flask's development server.
- Settings: `app/settings.py`, edited on the box when something changes.
- Geocoder: `geo.bank.internal`, resolved through `/etc/hosts` on web-02 (`vm/etc-hosts`).
- Database: the `branches` table in `bankwave` on `wave1-db`.
- Logs: `/var/log/branch-locator/app.log`; the directory and any existing log files are owned by `branch-locator`. When switching an existing host from root, run `useradd --system --no-create-home --shell /sbin/nologin branch-locator && chown -R branch-locator:branch-locator /var/log/branch-locator` before `systemctl daemon-reload && systemctl restart branch-locator`. Otherwise the root-owned `app.log` cannot be opened and the unit restart-loops.
- Pages: `/` and `/api/nearest?q=<text>`.

In the wave stand-in, `make vm-up` serves it on http://localhost:8083/.
