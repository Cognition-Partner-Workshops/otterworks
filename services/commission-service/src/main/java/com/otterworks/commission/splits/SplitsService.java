package com.otterworks.commission.splits;

import java.math.BigDecimal;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.otterworks.commission.common.AuditLog;
import com.otterworks.commission.common.Guards;
import com.otterworks.commission.common.OraException;
import com.otterworks.commission.common.OracleText;

/** COMMISSION_PKG.set_commission_splits: rules R13-R21 (R37, R38 on numbers and text). */
@Service
public class SplitsService {

    private static final BigDecimal HUNDRED = BigDecimal.valueOf(100);

    private final SplitsRepository repo;
    private final Guards guards;
    private final AuditLog audit;

    public SplitsService(SplitsRepository repo, Guards guards, AuditLog audit) {
        this.repo = repo;
        this.guards = guards;
        this.audit = audit;
    }

    @Transactional
    public int setSplits(Long policyId, List<SplitAllocation> splits, String actor) {
        if (repo.policyStatus(policyId).isEmpty()) {
            throw new OraException(-20005, "Unknown policy: " + OracleText.toChar(policyId));
        }
        if (splits == null || splits.isEmpty()) {
            throw new OraException(-20006, "At least one split allocation is required");
        }
        // COUNT(DISTINCT agent_id) ignores NULL, so a NULL agent counts as a duplicate.
        Set<Long> distinct = new HashSet<>();
        splits.stream().map(SplitAllocation::agentId).filter(Objects::nonNull).forEach(distinct::add);
        if (distinct.size() != splits.size()) {
            throw new OraException(-20006, "Duplicate agent in split allocation");
        }

        BigDecimal total = BigDecimal.ZERO;
        for (SplitAllocation s : splits) {
            BigDecimal pct = s.splitPct();
            if (pct == null || pct.signum() <= 0 || pct.compareTo(HUNDRED) > 0) {
                throw new OraException(-20006,
                        "Split pct must be in (0, 100]: agent " + OracleText.toChar(s.agentId()));
            }
            guards.assertActiveAgent(s.agentId());
            total = total.add(pct);
        }
        if (total.compareTo(HUNDRED) != 0) {
            throw new OraException(-20006,
                    "Split percentages must total 100.00, got " + OracleText.toChar(total));
        }

        // Stored as given: NUMBER(5,2) rounds on insert, after the total was checked.
        repo.deleteSplits(policyId);
        for (SplitAllocation s : splits) {
            repo.insertSplit(policyId, s);
        }
        audit.log("SPLIT_SET", null, null, policyId, splits.size() + " agents", actor);
        return splits.size();
    }
}
