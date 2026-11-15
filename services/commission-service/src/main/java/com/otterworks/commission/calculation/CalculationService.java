package com.otterworks.commission.calculation;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.otterworks.commission.common.AuditLog;
import com.otterworks.commission.common.OraException;
import com.otterworks.commission.common.RateResolver;

/** COMMISSION_PKG.calculate_policy_commission (rules R25-R35, R37). */
@Service
public class CalculationService {

    public record Result(int rows) {
    }

    private final CalculationRepository repo;
    private final RateResolver rates;
    private final AuditLog audit;

    public CalculationService(CalculationRepository repo, RateResolver rates, AuditLog audit) {
        this.repo = repo;
        this.rates = rates;
        this.audit = audit;
    }

    /**
     * @param policyId   the policy id as the caller passed it (null allowed)
     * @param policyText TO_CHAR(p_policy_id), used in messages
     */
    @Transactional
    public Result calculate(BigDecimal policyId, String policyText, String periodMonth, String actor) {
        CalculationRepository.Policy policy = (policyId == null ? null : repo.findPolicy(policyId).orElse(null));
        if (policy == null) {
            throw new OraException(-20005, "Unknown policy: " + policyText);
        }
        if (!"IN_FORCE".equals(policy.status())) {
            throw new OraException(-20008, "Policy " + policyText + " is " + policy.status());
        }

        LocalDateTime asOf = repo.lastDayOfPeriod(periodMonth);

        repo.deleteLedger(policyId, periodMonth);

        int rows = 0;
        List<CalculationRepository.Split> splits = repo.splitsInOrder(policyId);
        for (CalculationRepository.Split split : splits) {
            long rateId = rates.resolve(policy.productCode(), split.agentId(), asOf);
            BigDecimal pct = repo.ratePct(rateId);
            BigDecimal amount = CommissionCalculator.commission(policy.annualPremium(), pct, split.splitPct());
            repo.insertLedger(policyId, split.agentId(), periodMonth, rateId, split.splitPct(),
                    policy.annualPremium(), amount);
            rows++;
        }

        if (rows == 0) {
            throw new OraException(-20006, "Policy " + policyText + " has no split allocation");
        }

        audit.log("COMMISSION_CALC", policy.productCode(), null, policyId.longValueExact(),
                (periodMonth == null ? "" : periodMonth) + " rows=" + rows, actor);
        return new Result(rows);
    }
}
