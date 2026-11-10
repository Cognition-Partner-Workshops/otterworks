package com.otterworks.commission.common;

import java.time.LocalDateTime;

/**
 * COMMISSION_PKG.resolve_rate: the rate_id in force for (product, agent, as_of),
 * or OraException -20007. Used by the calculation group; owned by the rates group.
 */
public interface RateResolver {

    long resolve(String productCode, Long agentId, LocalDateTime asOf);
}
