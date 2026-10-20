# rates-batch on rates-01

Builds the day's reference FX rates from the hourly tick files the market data feed drops overnight.

- OS: RHEL 7, OpenJDK 11 under `/usr/lib/jvm/java-11`.
- Install: `/opt/rates/lib/rates-batch.jar`, wrapper `/opt/rates/bin/run-rates.sh` (copy in `vm/`).
- Schedule: root's crontab, 02:00 every day (`vm/crontab`). The business date is "yesterday" on the host clock, and the host runs on local time.
- Input: `/var/spool/rates/in/ticks-<date>.csv`, written by the feed handler.
- Output: `/var/spool/rates/out/rates-<date>.csv`, exported over NFS and read by fx-report on report-01.
- Logs: `/var/log/rates/rates.log`, appended by the wrapper.
- Rerun a day by hand: `/opt/rates/bin/run-rates.sh 2026-10-15`.

In the wave stand-in, `make vm-up` mounts `../data/rates/in` as the input spool and shares the output spool with fx-report.
