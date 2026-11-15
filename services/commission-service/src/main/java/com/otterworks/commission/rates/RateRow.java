package com.otterworks.commission.rates;

import java.time.LocalDateTime;

/** A commission_rates row as far as rate resolution needs it. */
record RateRow(long rateId, Long agentId, LocalDateTime effectiveFrom, LocalDateTime effectiveTo) {
}
