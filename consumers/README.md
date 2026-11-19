# Legacy finance consumers

The [consumer registry](registry.yaml) records the teams, run cadence and
Teradata sources. Application readers connect through their own Teradata
drivers. Finance analysts use the [file-fed account status workbook](bi/README.md),
and the [partner extract](partner-extract/README.md) runs a separate BTEQ query,
validates its CSV and prepares a dry-run SFTP batch.

Use the [local warehouse quickstart](../warehouse/README.md) to generate a
sample landing feed and report files without external warehouse access.
