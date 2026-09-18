# 00_context.md

| Field | Value | Provenance |
|---|---|---|
| Source family | oracle (Oracle Database Free 23ai, schema OW_BILLING, PDB FREEPDB1) | DISCOVERED |
| Source estate | services/legacy-billing/db/oracle (DDL, PL/SQL packages, triggers, DBMS_SCHEDULER jobs) | FACT |
| Headline size | 19 tables, 155-column CUSTOMER_MASTER, 5 PL/SQL packages, 7 triggers, ~200k rows at demo scale | DISCOVERED |
| App repo | Cognition-Partner-Workshops/otterworks, services/legacy-billing/app (Flask, psycopg, reports via oracledb) | FACT |
| Driver language | Python 3.12 (pymongo, oracledb) | PROPOSED |
| Target | local Docker mongo:7 on this machine, database ow_billing, via MONGO_LOCAL_URI | FACT |
| Atlas project / cluster | none. recon_mode offline: no Atlas, no MCP, no MONGODB_ATLAS_URI | FACT |
| Children reach the source | no. Single session, no fan-out; loaders and recon run in this session only | FACT |
| Work branch | tp-run/mongodb-20260918T212022Z (base tech-partnerships); the only push and merge target | FACT |
| Stop routing | this session's parent session, via message_user | FACT |
| Stop mode | hard for STOP A, B, C (the run brief requires blocking on the reply) | FACT |
| Only pings | STOP A, STOP B, STOP C, final report | FACT |
| Plugin | mongo-migration-plugin, branch offline, checkout ~/mongo-migration-plugin | FACT |
