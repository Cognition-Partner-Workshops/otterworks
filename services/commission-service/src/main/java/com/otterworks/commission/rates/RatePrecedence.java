package com.otterworks.commission.rates;

import java.time.LocalDateTime;
import java.util.Comparator;
import java.util.List;
import java.util.Optional;

/**
 * resolve_rate's choice among candidate rows (R22, R23): the window
 * [effective_from, effective_to] contains as_of (effective_to NULL is open and
 * the end date is inclusive); an agent-specific row beats the product default
 * (ORDER BY agent_id NULLS LAST); within a scope the latest-starting row wins
 * (effective_from DESC).
 */
final class RatePrecedence {

    // The package's ORDER BY leaves ties on (agent_id, effective_from) to the
    // plan; rate_id ascending makes the pick deterministic.
    private static final Comparator<RateRow> ORDER = Comparator
            .comparing((RateRow r) -> r.agentId() == null)
            .thenComparing(RateRow::effectiveFrom, Comparator.reverseOrder())
            .thenComparingLong(RateRow::rateId);

    private RatePrecedence() {
    }

    static Optional<RateRow> pick(List<RateRow> candidates, Long agentId, LocalDateTime asOf) {
        if (asOf == null) {
            return Optional.empty();
        }
        return candidates.stream()
                .filter(r -> r.agentId() == null || (agentId != null && r.agentId().equals(agentId)))
                .filter(r -> !r.effectiveFrom().isAfter(asOf))
                .filter(r -> r.effectiveTo() == null || !r.effectiveTo().isBefore(asOf))
                .min(ORDER);
    }
}
