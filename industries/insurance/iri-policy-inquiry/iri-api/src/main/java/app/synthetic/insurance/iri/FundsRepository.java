package app.synthetic.insurance.iri;

import java.math.BigDecimal;
import java.sql.Date;
import java.time.LocalDate;
import java.util.List;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class FundsRepository {
    private final JdbcTemplate jdbc;

    public FundsRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public List<FundRow> funds(long contract) {
        return jdbc.query("SELECT f.fund_code, f.fund_name, f.unit_value, f.fund_value, v.valuation_date"
                        + " FROM fund_allocation f LEFT JOIN policy_values v ON v.contract_no = f.contract_no"
                        + " WHERE f.contract_no = ? ORDER BY f.fund_code",
                (rs, row) -> {
                    Date valuation = rs.getDate("valuation_date");
                    return new FundRow(rs.getString("fund_code"), rs.getString("fund_name"),
                            rs.getBigDecimal("unit_value"), rs.getBigDecimal("fund_value"),
                            valuation == null ? null : valuation.toLocalDate());
                }, contract);
    }

    public record FundRow(String fundCode, String fundName, BigDecimal unitValue, BigDecimal fundValue,
                          LocalDate valuationDate) {}
}
