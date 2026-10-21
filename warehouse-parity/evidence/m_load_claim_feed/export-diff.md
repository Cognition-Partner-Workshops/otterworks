# m_load_claim_feed: export diff (sqlserver vs snowflake)

## source

- columns: sqlserver ['claim_id', 'policy_number', 'status_code', 'reopen_date', 'claim_amount', 'loss_date'] / snowflake ['claim_id', 'policy_number', 'status_code', 'reopen_date', 'claim_amount', 'loss_date']
- rows: sqlserver 3000, snowflake 3000
- keys only in sqlserver: 0, only in snowflake: 0

| column | sqlserver value | snowflake value | rows |
|---|---|---|---|
| reopen_date | `1900-01-01` | `(empty = NULL)` | 2434 |

## LKP_claim_status

- columns: sqlserver ['status_code', 'status_desc'] / snowflake ['status_code', 'status_desc']
- rows: sqlserver 5, snowflake 5
- keys only in sqlserver: 0, only in snowflake: 0
- every column of every shared key identical


