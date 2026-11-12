package app.synthetic.insurance.iri;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.sql.Timestamp;
import java.time.LocalDate;
import java.util.Map;
import java.util.Set;

public final class ValuesMapper {
    static final int SCALE = 2;
    static final BigDecimal MAXIMUM = new BigDecimal("9999999999.99");
    static final Set<String> WITHDRAWAL_SOURCES = Set.of("WITHDRAWALS_TO_DATE");

    private final String withdrawalSource;

    public ValuesMapper(String withdrawalSource) {
        if (withdrawalSource == null || !WITHDRAWAL_SOURCES.contains(withdrawalSource)) {
            throw new IllegalStateException("Unsupported iri.provisional.values.withdrawal-source: " + withdrawalSource);
        }
        this.withdrawalSource = withdrawalSource;
    }

    public PolicyValue map(Map<String, Object> row) {
        return new PolicyValue(date(row.get("VALUATION_DATE")),
                new PolicyValue.AccountValues(amount(row, "ACCOUNT_VALUE"), amount(row, "SURRENDER_VALUE"),
                        amount(row, withdrawalSource)),
                amount(row, "PREMIUMS_TO_DATE"));
    }

    static LocalDate date(Object value) {
        if (value instanceof Timestamp timestamp) {
            return timestamp.toLocalDateTime().toLocalDate();
        }
        if (value instanceof java.sql.Date date) {
            return date.toLocalDate();
        }
        if (value instanceof LocalDate date) {
            return date;
        }
        throw new IllegalStateException("VALUATION_DATE is not a date");
    }

    static BigDecimal amount(Map<String, Object> row, String column) {
        Object value = row.get(column);
        if (value == null) {
            throw new IllegalStateException(column + " is missing");
        }
        BigDecimal amount = new BigDecimal(value.toString()).setScale(SCALE, RoundingMode.UNNECESSARY);
        // S-values-1: amounts outside the IRI 0..9999999999.99 range have no agreed representation.
        if (amount.signum() < 0 || amount.compareTo(MAXIMUM) > 0) {
            throw new UnmappedValue("policy.value.unmapped", column + " is outside the IRI amount range");
        }
        return amount;
    }
}
