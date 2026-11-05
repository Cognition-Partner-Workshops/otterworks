# Search Service

Full reindex uses the read-only `/internal/files/reindex` file-service endpoint.
Set the same random `FILE_REINDEX_TOKEN` in file-service, search-service, and the
weekly ETL job environment. Deployment scripts generate/reuse a per-namespace
credential and pass it to both Helm releases. For local Compose, export the
credential before starting the services; there is no default service password.
Source fetch errors, missing credentials, and invalid snapshots abort rebuilding
before either existing search index is replaced. The internal credential does
not authorize normal user listing or file mutations.

File-service also requires `FILE_REINDEX_OWNER_PREFIX`: the trusted, tenant-unique
prefix of the canonical UUID strings stored in DynamoDB `owner_id`. Set it through
the deployment environment or file-service Helm `config.FILE_REINDEX_OWNER_PREFIX`
(and the file-service environment for Compose). Namespace labels are not owner IDs;
the deploy scripts do not invent a mapping. Provision the prefix that matches the
tenant's existing owner allocation, never a shared or overlapping prefix.
The credential alone does not grant unscoped enumeration: an empty/whitespace
prefix returns 403, so the indexer aborts without clearing an index. DynamoDB filters
by that prefix before pagination and totals; request headers/query parameters
cannot change it. If an unscoped rebuild was previously run, rebuild with the
correct scope to replace any imported foreign metadata.
