package app.synthetic.insurance;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class JdbcInquiryRepository implements InquiryRepository {
    private final JdbcTemplate jdbc;

    public JdbcInquiryRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<Map<String, Object>> summary(long contract) {
        return jdbc.queryForList("SELECT * FROM annuity_policy WHERE contract_no = ?", contract).stream().findFirst();
    }

    public Optional<Map<String, Object>> values(long contract) {
        return jdbc.queryForList("SELECT * FROM policy_values WHERE contract_no = ?", contract).stream().findFirst();
    }

    public List<Map<String, Object>> funds(long contract) {
        return jdbc.queryForList("SELECT * FROM fund_allocation WHERE contract_no = ? ORDER BY fund_code", contract);
    }

    public List<Long> contracts() {
        return jdbc.queryForList("SELECT contract_no FROM annuity_policy ORDER BY contract_no", Long.class);
    }

    public void ping() {
        if (!Integer.valueOf(1).equals(jdbc.queryForObject("SELECT 1 FROM dual", Integer.class))) {
            throw new IllegalStateException("Database health check failed");
        }
    }
}
