package app.synthetic.insurance.iri.values;

import java.math.BigDecimal;

/** Maps POLICY_VALUES to PolicyValue with the legacy 15-digit, scale-2 amount rules. */
final class PolicyValueMapper {
    static final BigDecimal MAX_AMOUNT = new BigDecimal("9999999999999.99");

    private PolicyValueMapper() {}

    static PolicyValue map(PolicyValuesRow row) {
        return new PolicyValue(row.valuationDate(), amount(row.premiumsToDate()),
                new PolicyValue.AccountValues(amount(row.accountValue()), amount(row.surrenderValue()),
                        amount(row.withdrawalsToDate())),
                new PolicyValue.LegacyUnmappedValues(amount(row.cashValue()), amount(row.deathBenefit()),
                        amount(row.surrenderCharge())));
    }

    /** Same range the legacy API enforces (unsigned, 15 digits, 2 implied decimals); otherwise 400 like RTN_CD 08. */
    static BigDecimal amount(BigDecimal value) {
        BigDecimal scaled = value.setScale(2, java.math.RoundingMode.UNNECESSARY);
        if (scaled.signum() < 0 || scaled.compareTo(MAX_AMOUNT) > 0) {
            throw new IllegalArgumentException("Numeric field out of range");
        }
        return scaled;
    }
}
