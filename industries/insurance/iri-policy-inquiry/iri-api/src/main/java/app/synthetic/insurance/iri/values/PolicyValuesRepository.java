package app.synthetic.insurance.iri.values;

import java.util.Optional;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class PolicyValuesRepository {
    static final String SQL = "SELECT contract_no, valuation_date, account_value, surrender_value, cash_value,"
            + " premiums_to_date, withdrawals_to_date, death_benefit, surrender_charge"
            + " FROM policy_values WHERE contract_no = ?";

    private final JdbcTemplate jdbc;

    public PolicyValuesRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<PolicyValuesRow> find(long contractNo) {
        return jdbc.query(SQL, (rs, i) -> new PolicyValuesRow(rs.getLong("contract_no"),
                rs.getDate("valuation_date").toLocalDate(), rs.getBigDecimal("account_value"),
                rs.getBigDecimal("surrender_value"), rs.getBigDecimal("cash_value"),
                rs.getBigDecimal("premiums_to_date"), rs.getBigDecimal("withdrawals_to_date"),
                rs.getBigDecimal("death_benefit"), rs.getBigDecimal("surrender_charge")), contractNo)
                .stream().findFirst();
    }
}
