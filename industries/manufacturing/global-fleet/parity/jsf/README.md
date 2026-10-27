# JSF portal parity corpus

`requests.json` is an ordered, stateful corpus for the live Java 8 / JSF 2.2 Mojarra
portal. Each named context owns an independent `JSESSIONID` cookie jar. Form requests are
URL-encoded posts; `record.py` and `replay.py` scrape the current form name, generated field
names and `javax.faces.ViewState` from the preceding response before submitting a template.
Redirects are never followed automatically: the 302 and normalized `Location` are captured,
and a later explicit GET case requests that location.

`record.py` captures the baseline once. `replay.py` verifies `SHA256SUMS`, compares status,
normalized `Location`, and extracted HTML observations by default. `--strict` additionally
compares raw response bodies after normalizing ViewState, JSF session ids, generated ids,
and dates. The known recording date is 27 October 2026; the default statement period is
computed by the server as the previous month (2026-09 at capture time). The default-period
case normalizes only its period value, so it remains useful when the clock advances.

```sh
python3 record.py
python3 replay.py --stage first --out /path/to/evidence-first
python3 replay.py --stage full --out evidence
python3 replay.py --stage full --strict --out /path/to/evidence-strict
```

The wizard and statement use the same eligible, initially unassigned employee (`E1009100`,
Priya Raman). The request selects pool vehicle 1 (`HH-VS 7629`) and hands it over on
27.10.2026. Assignment cases use `E1009106` as the assigned example. The return flow uses
assigned plate `K-XE 9032` and separately checks unassigned pool plate `HH-VS 7629`.
After capturing the baseline, reset the tenant before full replay and again afterward:

```sh
industries/manufacturing/global-fleet/deploy/gf-tenant.sh reset
python3 replay.py --stage full --out evidence
industries/manufacturing/global-fleet/deploy/gf-tenant.sh reset
```

`recorded.json`, `SHA256SUMS`, and the committed reset/replay `evidence/SUMMARY.md` are
the replay baseline and evidence. No credentials are stored in this directory.
