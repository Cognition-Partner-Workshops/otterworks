# Global-fleet JSF refresh probe

- Local target: `http://127.0.0.1:18080`
- Tomcat container: `gf-refresh-tomcat`
- PostgreSQL container: `gf-refresh-db`
- Seed reset before each scenario: `001_schema.sql` then `002_seed.sql`
- Requests are not automatically redirected; repeated requests reuse the captured method, URL, body, ViewState, and Cookie header.

| Scenario | Action | HTTP status | Step rendered / error | DB counts after |
|---|---|---:|---|---|
| S1 | S1 initial GET /request.xhtml | 200 | 1 Mitarbeiter | — |
| S1 | S1 submit employee to render step 2 | 200 | 2 Fahrzeug | — |
| S1 | S1 F5 identical employee POST | 200 | 2 Fahrzeug | — |
| S1 | S1 address-bar GET after POST | 200 | 1 Mitarbeiter | — |
| S2 | S2 initial GET /request.xhtml | 200 | 1 Mitarbeiter | — |
| S2 | S2 submit employee to render step 2 | 200 | 2 Fahrzeug | — |
| S2 | S2 choose pool vehicle 1 to render step 3 | 200 | 3 Bestaetigung | — |
| S2 | S2 F5 identical chooseVehicle POST | 200 | 3 Bestaetigung | — |
| S2 | S2 address-bar GET after chooseVehicle POST | 200 | 1 Mitarbeiter | — |
| S3 | S3 initial GET /request.xhtml | 200 | 1 Mitarbeiter | — |
| S3 | S3 submit employee to render step 2 | 200 | 2 Fahrzeug | — |
| S3 | S3 choose vehicle 1 to render step 3 | 200 | 3 Bestaetigung | — |
| S3 | S3 submit #1 | 302; Location: /assignment.xhtml?employee=E1009100 | (none) | E1009100 assignments=1; vehicle 1 assignments=2; E1009100 car_request rows=1; vehicle 1 owner_employee_id=1 |
| S3 | S3 identical submit #2 | 200 | 1 Mitarbeiter | E1009100 assignments=1; vehicle 1 assignments=2; E1009100 car_request rows=1; vehicle 1 owner_employee_id=1 |
| S3 | S3 identical submit #3 after 302 | 200 | 1 Mitarbeiter | E1009100 assignments=1; vehicle 1 assignments=2; E1009100 car_request rows=1; vehicle 1 owner_employee_id=1 |
| S4 | S4 session A initial GET /request.xhtml | 200 | 1 Mitarbeiter | — |
| S4 | S4 session A employee step | 200 | 2 Fahrzeug | — |
| S4 | S4 session A choose vehicle 1 / reach step 3 | 200 | 3 Bestaetigung | — |
| S4 | S4 session B initial GET /request.xhtml | 200 | 1 Mitarbeiter | — |
| S4 | S4 session B employee step | 200 | 2 Fahrzeug | — |
| S4 | S4 session B choose vehicle 1 / reach step 3 | 200 | 3 Bestaetigung | — |
| S4 | S4 session B complete request first | 302; Location: /assignment.xhtml?employee=E1009103 | (none) | E1009100 assignments=0; vehicle 1 assignments=2; E1009100 car_request rows=0; vehicle 1 owner_employee_id=2 |
| S4 | S4 session A submits stale step-3 request | 302; Location: /assignment.xhtml?employee=E1009100 | (none) | E1009100 assignments=1; vehicle 1 assignments=3; E1009100 car_request rows=1; vehicle 1 owner_employee_id=1 |
| S5 | S5 initial GET /request.xhtml | 200 | 1 Mitarbeiter | — |
| S5 | S5 employee POST renders step 2 | 200 | 2 Fahrzeug | — |
| S5 | S5 replay step-2-rendering POST after Tomcat restart | 200 | 2 Fahrzeug | — |
| S5 | S5 plain GET after Tomcat restart and replay | 200 | 1 Mitarbeiter | — |

## Scenario notes

- **S1:** S1 F5 rendered 2 Fahrzeug; address-bar GET rendered 1 Mitarbeiter; GET issued a new ViewState.
- **S2:** S2 chooseVehicle replay rendered 3 Bestaetigung; address-bar GET rendered 1 Mitarbeiter; GET issued a new ViewState.
- **S4:** Session B employee was E1009103 (id 2, grade 9).
- **S5:** After restart, replay returned HTTP 200 (2 Fahrzeug); plain GET returned HTTP 200 and rendered 1 Mitarbeiter.

## Evidence

The 79 numbered HTTP traces are committed under
`industries/manufacturing/global-fleet/parity/jsf/refresh-probe/evidence/`:

- [S1](evidence/S1/)
- [S2](evidence/S2/)
- [S3](evidence/S3/)
- [S4](evidence/S4/)
- [S5](evidence/S5/)

Each `.txt` file contains the request method/URL/headers/cookie/body and response
status/headers/Location/full body.
DB snapshots are appended to the corresponding submit response evidence file.
