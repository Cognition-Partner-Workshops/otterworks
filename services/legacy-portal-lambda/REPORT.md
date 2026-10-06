# legacy-portal replay against the recorded Java responses

Target: `https://vxlourvu9b.execute-api.us-east-1.amazonaws.com/`

Java: `java-reference.json` (recorded capture)

Stage: `full`

Started (UTC): 2026-10-05T16:21:27Z

| Context | Cases in corpus | Cases run | Identical | Different | First divergence | Result |
|---|---|---|---|---|---|---|
| common | 10 | 10 | 10 | 0 | - | all identical |
| announcements | 36 | 36 | 36 | 0 | - | all identical |
| preferences | 20 | 20 | 20 | 0 | - | all identical |
| feedback | 29 | 29 | 29 | 0 | - | all identical |

95/95 replayed cases identical.

Run after merging the announcements (780f5f18), preferences (5199bb48) and feedback (e93c4cd7) branches and `make lp-reset RUN=lp-20261005-mp CTX=all`. Deployed function code was checked against a rebuild of the merged tree (same class and resource files); no redeploy.
