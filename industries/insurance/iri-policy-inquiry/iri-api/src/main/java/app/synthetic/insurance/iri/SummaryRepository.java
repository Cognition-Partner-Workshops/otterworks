package app.synthetic.insurance.iri;

import java.util.Map;
import java.util.Optional;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class SummaryRepository {
    private static final String SQL = "SELECT status_code, product_name, plan_code, qualification_code,"
            + " issue_state, currency_code, effective_date FROM annuity_policy WHERE contract_no = ?";

    private final JdbcTemplate jdbc;

    public SummaryRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<Map<String, Object>> find(long contract) {
        return jdbc.queryForList(SQL, contract).stream().findFirst();
    }
}
