package com.otterworks.commission.splits;

import java.math.BigDecimal;

import com.fasterxml.jackson.annotation.JsonProperty;

/** One split_alloc_t element: agent_id and split_pct, either may be NULL. */
public record SplitAllocation(
        @JsonProperty("agent_id") Long agentId,
        @JsonProperty("split_pct") BigDecimal splitPct) {
}
