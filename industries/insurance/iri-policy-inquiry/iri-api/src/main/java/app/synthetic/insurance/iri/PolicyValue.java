package app.synthetic.insurance.iri;

import java.math.BigDecimal;
import java.time.LocalDate;

public record PolicyValue(LocalDate valuesAsOfDate, AccountValues accountValues, BigDecimal totalDepositITD) {
    public record AccountValues(BigDecimal endingAccountValue, BigDecimal surrenderValue,
                                BigDecimal totalNetWithdrawalSinceIssue) {}
}
