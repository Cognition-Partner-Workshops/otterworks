# analytics_daily goldens

Each directory is one scenario (`scenario.json` + `golden/`). Run date `ds` is
the UTC date of `frozen_time`: 2026-03-15 everywhere. Behavior below is the
legacy behavior as recorded, bugs included.

| scenario | seed | what it pins |
|---|---|---|
| `smoke` | 4 SQS + 1 malformed, 2 DynamoDB for ds + 1 other date | harness smoke (from the harness PR) |
| `full_day` | 24 valid + 3 malformed SQS bodies (27 messages, several receive batches of up to 10), 6 DynamoDB items for ds (one with `event_date` `2026-03-15T21:30:00Z`), 3 for other dates | hour bucketing across 15 hours; user-field precedence `ownerId` > `editedBy` > `authorId` > `deletedBy` > `userId` with empty strings skipped; events with no user field counted as `unknown` (left out of `active_users`, listed in `top_users`); SQS events dated the day before are counted; DynamoDB events for other dates are excluded; DynamoDB `event_type` lost (`NaN`) because SQS bodies carry `eventType`; malformed bodies left in flight |
| `dynamodb_only` | DynamoDB only, same items as `full_day` | `event_type` copied to `eventType` when no SQS body has `eventType`; float `sizeBytes` (10.5) truncated by `int()` of the sum |
| `empty_input` | nothing | "No events found", exit 0, no S3 object, no Postgres row |
| `no_events_for_ds` | 2 malformed SQS bodies, DynamoDB items for other dates only | same early exit; malformed bodies left in flight |
| `rerun_upsert` | 3 SQS events; Postgres rows for ds (stale) and 2026-03-14; stale S3 objects at the output keys plus an unrelated key under the partition | ds row overwritten by `ON CONFLICT (report_date) DO UPDATE` with this run's numbers only (no merge with the earlier run); previous day's row untouched; output keys overwritten, other keys under the partition kept |
| `postgres_unavailable` | 3 SQS events; `database.password` overridden | upsert error logged and swallowed; S3 outputs and report still written; exit 0, no row |
| `sqs_non_object_body` | 3 SQS events + a body `42` | valid-JSON non-object accepted and deleted, then `pandas.DataFrame` raises: FATAL, exit 1, nothing written, queue empty (events lost) |

The SQS surface is message counts only: `in_flight` is malformed bodies that
were received and never deleted (30 s visibility timeout).
