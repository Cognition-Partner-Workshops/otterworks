# OtterWorks Workbench

Run the app in Docker with `make workbench-up`, then open http://localhost:3002/. Run `make workbench-down` to stop it. For hot reload, run `npm ci` and `npm run dev` from `frontend/workbench`.

The root Compose file references services from `docker-compose.infra.yml`. A bare `docker compose up workbench` command needs both `-f docker-compose.infra.yml -f docker-compose.yml` options, as in `docker compose -f docker-compose.infra.yml -f docker-compose.yml up -d --build --no-deps workbench`.

The fixture data lives in `src/fixtures/fixtures.ts`, where you can update the local demo records. Board changes and chat messages stay in browser localStorage. Select Reset demo data to restore the fixture state.

## Deep links

- Home page: `/`
- Project list: `/boards`
- OW project: `/boards/OW`
- OW-42 issue: `/boards/OW/OW-42`
- OW-38 issue: `/boards/OW/OW-38`
- SEC-12 issue: `/boards/SEC/SEC-12`
- SEC-11 issue: `/boards/SEC/SEC-11`
- MOD-11 issue: `/boards/MOD/MOD-11`
- MOD-8 issue: `/boards/MOD/MOD-8`
- Chat redirect: `/chat`
- Incidents channel: `/chat/incidents`
- Incident thread p1001: `/chat/incidents/t/p1001`
- Incident thread p1002: `/chat/incidents/t/p1002`
- Security thread p2001: `/chat/security/t/p2001`
- Security thread p2002: `/chat/security/t/p2002`
- Modernization discussion p3001: `/chat/modernization/t/p3001`
- Modernization thread p3002: `/chat/modernization/t/p3002`
- Modernization follow-up p3003: `/chat/modernization/t/p3003`
- ITSM redirect: `/itsm`
- Incident list: `/itsm/incidents`
- INC0010042 record: `/itsm/incidents/INC0010042`
- INC0010043 record: `/itsm/incidents/INC0010043`
- Problem list: `/itsm/problems`
- PRB0040008 record: `/itsm/problems/PRB0040008`
- Change list: `/itsm/changes`
- CHG0030017 record: `/itsm/changes/CHG0030017`
- CHG0030026 record: `/itsm/changes/CHG0030026`
- Service list: `/itsm/services`
- document-service record: `/itsm/services/document-service`
- legacy-billing record: `/itsm/services/legacy-billing`
- Unknown route: `/unknown/workbench/route`

GitHub Pages builds use `/otterworks/` as the base path. Vite also copies `index.html` to `404.html` so a refresh on a deep link returns the app shell.
