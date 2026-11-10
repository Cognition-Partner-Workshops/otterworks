package com.otterworks.commission.rates;

import java.math.BigDecimal;
import java.time.LocalDateTime;

import com.otterworks.commission.common.AuditLog;
import com.otterworks.commission.common.Guards;
import com.otterworks.commission.common.OraException;
import com.otterworks.commission.common.OracleText;
import com.otterworks.commission.common.RateResolver;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * upsert_commission_rate (R1-R9), end_commission_rate (R10-R12) and resolve_rate
 * (R22-R24). Each write runs in one transaction: any rejection or database error
 * rolls back everything the call wrote (R9).
 */
@Service
public class RatesService {

    private static final BigDecimal MAX_RATE = new BigDecimal("50");

    private final RateRepository rates;
    private final Guards guards;
    private final AuditLog audit;
    private final RateResolver resolver;

    public RatesService(RateRepository rates, Guards guards, AuditLog audit, RateResolver resolver) {
        this.rates = rates;
        this.guards = guards;
        this.audit = audit;
        this.resolver = resolver;
    }

    @Transactional
    public long upsert(String productCode, Long agentId, BigDecimal ratePct, LocalDateTime effectiveFrom,
            String actor) {
        if (ratePct == null || ratePct.signum() <= 0 || ratePct.compareTo(MAX_RATE) > 0) {
            throw new OraException(-20001,
                    "Rate must be in (0, 50]: " + (ratePct == null ? "NULL" : OracleText.toChar(ratePct)));
        }
        guards.assertProduct(productCode);
        if (agentId != null) {
            guards.assertActiveAgent(agentId);
        }

        Long rateId = rates.amendSameDay(productCode, agentId, ratePct, effectiveFrom, actor);
        if (rateId == null) {
            rates.closeOpenStartedBefore(productCode, agentId, effectiveFrom,
                    effectiveFrom == null ? null : effectiveFrom.minusDays(1));
            rateId = rates.insertOpen(productCode, agentId, ratePct, effectiveFrom, actor);
        }

        audit.log("RATE_UPSERT", productCode, agentId, null,
                "rate_id=" + rateId + " pct=" + OracleText.toChar(ratePct)
                        + " from=" + OracleText.isoDay(effectiveFrom),
                actor);
        return rateId;
    }

    @Transactional
    public void end(String productCode, Long agentId, LocalDateTime effectiveTo, String actor) {
        if (rates.endOpen(productCode, agentId, effectiveTo) == 0) {
            throw new OraException(-20007,
                    "No open rate for " + (productCode == null ? "" : productCode) + "/"
                            + (agentId == null ? "default" : OracleText.toChar(agentId)));
        }
        audit.log("RATE_END", productCode, agentId, null, "to=" + OracleText.isoDay(effectiveTo), actor);
    }

    public long resolve(String productCode, Long agentId, LocalDateTime asOf) {
        return resolver.resolve(productCode, agentId, asOf);
    }
}
