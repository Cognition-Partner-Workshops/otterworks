package com.otterworks.commission.rates;

import java.time.LocalDateTime;

import com.otterworks.commission.common.OraException;
import com.otterworks.commission.common.OracleText;
import com.otterworks.commission.common.RateResolver;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

/** COMMISSION_PKG.resolve_rate read from commission_rates (R22-R24). */
@Component
public class JdbcRateResolver implements RateResolver {

    private final RateRepository rates;

    public JdbcRateResolver(RateRepository rates) {
        this.rates = rates;
    }

    @Override
    @Transactional
    public long resolve(String productCode, Long agentId, LocalDateTime asOf) {
        return RatePrecedence.pick(rates.candidates(productCode, agentId), agentId, asOf)
                .map(RateRow::rateId)
                .orElseThrow(() -> new OraException(-20007,
                        "No rate in force for " + nullToEmpty(productCode) + "/agent "
                                + (agentId == null ? "default" : OracleText.toChar(agentId))
                                + " on " + OracleText.isoDay(asOf)));
    }

    private static String nullToEmpty(String s) {
        return s == null ? "" : s;
    }
}
