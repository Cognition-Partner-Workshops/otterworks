package com.otterworks.commission.splits;

import java.util.List;
import java.util.Optional;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class SplitsRepository {

    private final JdbcTemplate jdbc;

    public SplitsRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<String> policyStatus(Long policyId) {
        List<String> status = jdbc.queryForList(
                "SELECT status FROM policies WHERE policy_id = ?", String.class, policyId);
        return status.stream().findFirst();
    }

    public void deleteSplits(Long policyId) {
        jdbc.update("DELETE FROM commission_splits WHERE policy_id = ?", policyId);
    }

    public void insertSplit(Long policyId, SplitAllocation split) {
        jdbc.update("INSERT INTO commission_splits (policy_id, agent_id, split_pct) VALUES (?, ?, ?)",
                policyId, split.agentId(), split.splitPct());
    }
}
