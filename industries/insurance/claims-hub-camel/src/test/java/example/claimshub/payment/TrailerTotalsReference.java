package example.claimshub.payment;

/**
 * Test oracle: {@code TrailerTotalsComponent.Check} from Pipelines/Components/TrailerTotalsComponent.cs, line
 * for line. {@code long.Parse} becomes {@link Long#parseLong(String)}; both throw on text that is not an
 * integer (the C# component lets the FormatException suspend the message, so does this).
 */
final class TrailerTotalsReference {

    private TrailerTotalsReference() {
    }

    /** {@code null} when the trailer agrees with the body, otherwise the name of the first field that does not. */
    static String check(String file) {
        int count = 0;
        long debit = 0;
        long credit = 0;
        String trailer = null;
        for (String raw : file.split("\r\n")) {
            if (raw.isEmpty()) {
                continue;
            }
            if (raw.startsWith("PAY")) {
                count++;
                long cents = Long.parseLong(raw.substring(57, 69));
                if (raw.charAt(69) == 'C') {
                    credit += cents;
                } else {
                    debit += cents;
                }
            } else if (raw.startsWith("TRL")) {
                trailer = raw;
            }
        }
        if (trailer == null) {
            return "no TRL record";
        }
        if (Long.parseLong(trailer.substring(3, 9)) != count) {
            return "PaymentCount";
        }
        if (Long.parseLong(trailer.substring(9, 23)) != debit) {
            return "DebitTotalCents";
        }
        if (Long.parseLong(trailer.substring(23, 37)) != credit) {
            return "CreditTotalCents";
        }
        if (Long.parseLong(trailer.substring(37, 47)) != (debit + credit) % 10000000000L) {
            return "HashTotal";
        }
        return null;
    }

    /** What the legacy send pipeline does with this file: {@code null} if it sends it, otherwise why it suspends it. */
    static String legacyVerdict(String file) {
        try {
            return check(file);
        } catch (NumberFormatException e) {
            return "long.Parse throws: " + e.getMessage();
        }
    }
}
