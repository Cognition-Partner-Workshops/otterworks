package example.claimshub.maps;

import java.math.BigDecimal;
import java.math.RoundingMode;

/** Money as the claims hub's C# functoids wrote it: invariant culture, {@code 0.00}, rounded half to even. */
final class Money {

    private Money() {
    }

    /** {@code Convert.ToDecimal(s, InvariantCulture)} / {@code xs:decimal(s)} for the plain decimal literals in the corpus. */
    static BigDecimal parse(String amount) {
        return new BigDecimal(amount.strip());
    }

    /** {@code Math.Round(value, 2).ToString("0.00", InvariantCulture)}; .NET {@code Math.Round} is banker's rounding. */
    static String format(BigDecimal value) {
        return value.setScale(2, RoundingMode.HALF_EVEN).toPlainString();
    }
}
