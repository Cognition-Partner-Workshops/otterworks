# Identity and status parity

`10_load.sql` converts `03_load_identity.bteq` as two delete/insert full
refreshes with explicit source-order columns. No deduplication, case folding,
date coercion, or timezone conversion is introduced. No views or Python hook
are needed.

The final code columns are Teradata CHAR(12), unlike the VARCHAR staging
columns. RPAD explicitly preserves their trailing spaces in Snowflake VARCHAR
storage and in DuckDB. Owner question: retain padding or normalize consumers?
Default: retain the source's 12-character representation. Oversize code values
and rejected input records are outside this valid-landing parity proof.

The two FastLoads land five pipe-separated fields apiece into their respective
typed `STG_` tables. The local board supplies those staging inputs, then runs
the converted SQL independently to build the final tables. Green staging and
FastLoad rows therefore prove equality at the typed landing boundary, not
Snowflake file ingestion, error-file handling, or FastLoad session/ERRLIMIT
behavior. Snowflake execution remains unverified and red.

Owner questions and defaults:

- Should provider/status code comparisons preserve Teradata NOT CASESPECIFIC
  semantics? Default: preserve input spelling; this load performs no comparisons.
- How should duplicate/non-null primary-index violations be handled in Snowflake,
  where standard-table uniqueness is not enforced? Default: do not silently
  deduplicate; retain the source delete/insert semantics. The board measures row
  multiplicity, not enforcement of Teradata constraints on invalid inputs.
- Should the two refreshes be atomic together? Default: preserve the source's
  separate statements rather than introduce a new transaction boundary.

Dates remain DATE values, including null open-ended VALID_TO; no timestamp or
timezone policy is required by these source schemas.
