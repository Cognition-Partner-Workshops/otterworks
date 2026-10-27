# JSF portal parity corpus

`requests.json` is an ordered, stateful corpus for the live Java 8 / JSF 2.2 Mojarra
portal. Each named context owns an independent `JSESSIONID` cookie jar. Form requests are
URL-encoded posts; `record.py` and `replay.py` scrape the current form name, generated field
names and `javax.faces.ViewState` from the preceding response before submitting a template.
Redirects are never followed automatically: the 302 and normalized `Location` are captured,
and a later explicit GET case requests that location.

`record.py` captures the baseline once. `replay.py` verifies `SHA256SUMS`, compares status,
media type, normalized `Location`, and extracted HTML observations by default. The
observations include whitespace-collapsed visible body text (excluding scripts and styles).
For non-HTML responses, the normalized body is also compared by default; `--strict`
additionally compares normalized raw HTML bodies after normalizing ViewState, JSF session
ids, generated ids, and dates.

`recorded.json` stores `recordedOn` (`2026-10-27`). For each replay response, `replay.py`
reads the HTTP `Date` header and converts it to the portal JVM's `Etc/UTC` day. It maps
both `dd.MM.yyyy` and `yyyy-MM-dd` spellings of the recording day and replay day to
`<today>` on both sides. The timezone source is `jsf-portal/Dockerfile`: it uses the
Tomcat JRE 8 image without a `TZ` or JVM timezone override; the live portal container's
`/etc/localtime` points to `Etc/UTC` and its system clock reports `UTC +0000`.
`--replay-day YYYY-MM-DD` overrides the response-derived day for offline tests.

The corpus explicitly submits `27.10.2026`; because that is also the recording day, it is
normalized to `<today>`. This is a known limitation: replay will not detect a change to
that explicit submitted date alone. The default statement period is computed by the
server as the previous month (2026-09 at capture time); its case normalizes that period
value so it remains useful as the clock advances. `MileageBean.refresh` fetches claims
from six months before its current date through today. That moving list content is
intentionally not normalized and can change as the clock advances.

```sh
python3 record.py
python3 selftest.py
python3 replay.py --stage first --out /path/to/evidence-first
python3 replay.py --stage full --out evidence
python3 replay.py --stage full --strict --out /path/to/evidence-strict
```

`selftest.py` is offline; it checks health/media-type and wizard-text changes, a
recording-day to replay-day shift, and equivalence of all 40 unmodified responses.

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
