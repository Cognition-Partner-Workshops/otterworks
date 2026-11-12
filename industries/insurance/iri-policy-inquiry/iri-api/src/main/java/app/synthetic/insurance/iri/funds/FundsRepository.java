package app.synthetic.insurance.iri.funds;

import java.math.BigDecimal;
import java.sql.Timestamp;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class FundsRepository {
    private final JdbcTemplate jdbc;

    public FundsRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public List<PolicyFunds.Fund> funds(BigDecimal contract) {
        List<Map<String, Object>> rows = jdbc.queryForList(
                "SELECT * FROM fund_allocation WHERE contract_no = ? ORDER BY fund_code", contract);
        if (rows.isEmpty()) {
            return List.of();
        }
        List<Map<String, Object>> values = jdbc.queryForList(
                "SELECT valuation_date FROM policy_values WHERE contract_no = ?", contract);
        String valuationDate = values.isEmpty() ? null : date(values.get(0).get("VALUATION_DATE"));
        return rows.stream().map(row -> new PolicyFunds.Fund(
                (String) row.get("FUND_CODE"), (String) row.get("FUND_NAME"),
                decimal(row.get("UNIT_VALUE")), decimal(row.get("FUND_VALUE")), valuationDate,
                List.of(new PolicyFunds.Segment(decimal(row.get("FUND_UNITS")))))).toList();
    }

    private static BigDecimal decimal(Object value) {
        return value == null ? null : new BigDecimal(value.toString());
    }

    private static String date(Object value) {
        LocalDate date = value instanceof Timestamp timestamp ? timestamp.toLocalDateTime().toLocalDate()
                : value instanceof java.sql.Date sqlDate ? sqlDate.toLocalDate() : (LocalDate) value;
        return date.toString();
    }
}
