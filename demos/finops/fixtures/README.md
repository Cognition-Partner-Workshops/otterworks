# Synthetic billing and change snapshots

The billing export uses two matched seven-day UTC windows with synthetic USD rates. Filter by run tag, environment and usage type. The run tag labels the export scope; a blank service and resource ID mean the underlying charge has no allocation tag.

Workload requests are the same daily fleet count on each attributed line. Count requests once per day for the fleet total. The log line models stored byte-days at steady state and excludes ingest and retention run-in.

`fixtureJoin` adds repository metadata to the synthetic CloudTrail records. Find the configuration commit with `git log --find-object=<source_blob> -- <source_path>`. The blob identifies identical file contents after a squash merge.

The two SNS envelopes carry the same Cost Anomaly ID but different SNS delivery IDs. Neither envelope comes from a live account.
