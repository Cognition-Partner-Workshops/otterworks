# account-events — BW6 process inventory

Run tib-d1111, base commit `5c2ba511babbfacaba94c93a10d3e6b0542a7c4c`. All five processes share `EmsConnection` and `LedgerJdbc` and the `common/receipt.xsl` transform; all are proposed **needs-human-decision**.

| Process | Spec | One line |
|---|---|---|
| `halvergate.account-events.account-closed` | [account-closed.md](account-closed.md) | Durable topic `HB.ACCOUNT.CLOSED` → receipt (`ACCOUNT_CLOSED`) → INSERT `account_closures` → queue `HB.ACCOUNT.ARCHIVED` [`integration/legacy-bw6/Processes/account-events/account-closed.bwp:L14`](../../../../legacy-bw6/Processes/account-events/account-closed.bwp#L14) |
| `halvergate.account-events.account-opened` | [account-opened.md](account-opened.md) | Durable topic `HB.ACCOUNT.OPENED` → receipt (`ACCOUNT_OPENED`) → INSERT `account_registry` → queue `HB.ACCOUNT.CREATED` [`integration/legacy-bw6/Processes/account-events/account-opened.bwp:L14`](../../../../legacy-bw6/Processes/account-events/account-opened.bwp#L14) |
| `halvergate.account-events.address-changed` | [address-changed.md](address-changed.md) | Durable topic `HB.ADDRESS.CHANGED` → receipt (`ADDRESS_CHANGED`) → INSERT `account_addresses` → queue `HB.ADDRESS.UPDATED` [`integration/legacy-bw6/Processes/account-events/address-changed.bwp:L14`](../../../../legacy-bw6/Processes/account-events/address-changed.bwp#L14) |
| `halvergate.account-events.event-fanout` | [event-fanout.md](event-fanout.md) | Queue receiver `HB.ACCOUNT.EVENTS.IN` → receipt (`EVENT_FANOUT`) → INSERT `account_events` → topic `HB.ACCOUNT.EVENTS` → calls the other four processes [`integration/legacy-bw6/Processes/account-events/event-fanout.bwp:L14`](../../../../legacy-bw6/Processes/account-events/event-fanout.bwp#L14) |
| `halvergate.account-events.limit-changed` | [limit-changed.md](limit-changed.md) | Durable topic `HB.LIMIT.CHANGED` (per-`accountId` ordering) → receipt (`LIMIT_CHANGED`) → INSERT `account_limits` → queue `HB.LIMIT.UPDATED` [`integration/legacy-bw6/Processes/account-events/limit-changed.bwp:L14`](../../../../legacy-bw6/Processes/account-events/limit-changed.bwp#L14) |
