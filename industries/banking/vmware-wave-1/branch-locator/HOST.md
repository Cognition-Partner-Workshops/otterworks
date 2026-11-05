# branch-locator on web-02

The "find a branch" page on the public site. Takes a postcode or district, asks the internal geocoder for coordinates, and lists the three nearest branches with whether they are open now.

- Host prerequisite (owner handover): provision Python 3.12 on web-02 and create `/opt/branch-locator/venv` with `python3.12 -m venv /opt/branch-locator/venv`; install `requirements.txt` with `/opt/branch-locator/venv/bin/python -m pip install -r /opt/branch-locator/requirements.txt` before restarting the unit. The legacy CentOS 7 system Python is not used by the service.
- Install: `/opt/branch-locator/app`, started by systemd (`vm/branch-locator.service`) as the unprivileged `branch-locator` user, served by waitress (`app/server.py`) rather than Flask's development server.
- Settings: `app/settings.py`, edited on the box when something changes.
- Geocoder: `geo.bank.internal`, resolved through `/etc/hosts` on web-02 (`vm/etc-hosts`).
- Database: the `branches` table in `bankwave` on `wave1-db`.
- Logs: `/var/log/branch-locator/app.log`; the directory and any existing log files are owned by `branch-locator`. When switching an existing host from root, run `useradd --system --no-create-home --shell /sbin/nologin branch-locator && chown -R branch-locator:branch-locator /var/log/branch-locator` before `systemctl daemon-reload && systemctl restart branch-locator`. Otherwise the root-owned `app.log` cannot be opened and the unit restart-loops.
- Pages: `/` and `/api/nearest?q=<text>`.

In the wave stand-in, `make vm-up` serves it on http://localhost:8083/.

Runtime pin changes: `waitress==3.0.2` replaces 1.4.4 to pick up the serving security fixes and requires Python 3; `psycopg2-binary==2.9.9` replaces 2.8.6 as the first release with Python 3.12 wheels. All other direct dependency pins are retained.
