# Incident MCP adapters

The local adapters query the existing incident stack. Grafana MCP uses Grafana's provisioned Prometheus datasource (`Prometheus`), and Postgres MCP reads the same `otterworks` database as document-service. Start the incident stack first; the workspace README includes the Compose command.

For a local alert storm, the same adapters can inspect concurrently armed
scenarios (`make arm SCENARIO=all`). Batch webhook configuration belongs to
mock Slack; adapter credentials and query endpoints stay unchanged.

## Start the adapters

Set `GRAFANA_SERVICE_ACCOUNT_TOKEN` to a Viewer token and `DATABASE_URI` to the local database connection string. For a disposable local stack, the existing Grafana login can instead come from `GRAFANA_USERNAME` and `GRAFANA_PASSWORD`. Prefer the Viewer token. The local stack's development database URL is `postgresql://otterworks:otterworks_dev@127.0.0.1:5432/otterworks`; a restricted login is preferable even though the MCP server also enforces restricted access mode.

```sh
make -C demo-platform/collection mcp-up
make -C demo-platform/collection mcp-smoke
```

The adapters use Linux host networking and bind to loopback. `grafana/mcp-grafana:0.9.0` listens at `http://127.0.0.1:8000/sse`, with write tools disabled and only search, datasource, Prometheus and dashboard categories enabled. `postgres-mcp==0.3.0` listens at `http://127.0.0.1:8001/sse` with `--access-mode=restricted`. The database driver reads `DATABASE_URI` from the environment. Neither endpoint should be exposed publicly without a separate authenticated gateway.

Import `client.json` into a local SSE-capable MCP client, adapting the client's transport field if needed. Cloud-hosted MCP marketplace integrations need a separate connectivity check. A remote integration requires an already-reachable target or a supported machine-local execution option; verify a real query before recording a connection as successful.

## Database permissions

Create a database login with `reader.sql` before starting the MCP adapter when the local database will outlive a disposable run. Supply a generated password with psql's `reader_password` variable without logging the command or password. The grants cover current and future tables created by the `otterworks` role in `public`, restrict default transactions to read-only and limit statements to ten seconds. Point `DATABASE_URI` at the restricted login. The SQL fails if the role already exists, preserving any existing password.

The smoke query reads `current_database()` and the document count, and the telemetry query runs PromQL `up` through Grafana. Successful protocol initialization must be followed by a successful target query. Store query results in the session's verification evidence.

Stop adapters with `make -C demo-platform/collection mcp-down`, keeping `DATABASE_URI` set so Compose can validate the configuration. Drop the temporary reader login after disconnecting the adapter, or remove the entire disposable incident volume when teardown permits. No cloud resources are required.

Sources: [Grafana MCP 0.9.0](https://github.com/grafana/mcp-grafana/tree/v0.9.0) and [Postgres MCP 0.3.0](https://github.com/crystaldba/postgres-mcp/tree/v0.3.0).
