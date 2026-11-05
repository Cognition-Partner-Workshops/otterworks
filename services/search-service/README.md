# Search Service

Full reindex uses the read-only `/internal/files/reindex` file-service endpoint.
Set the same random `FILE_REINDEX_TOKEN` in file-service, search-service, and the
weekly ETL job environment. Deployment scripts generate/reuse a per-namespace
credential and pass it to both Helm releases. For local Compose, export the
credential before starting the services; there is no default service password.
Source fetch errors, missing credentials, and invalid snapshots abort rebuilding
before either existing search index is replaced. The internal credential does
not authorize normal user listing or file mutations.
