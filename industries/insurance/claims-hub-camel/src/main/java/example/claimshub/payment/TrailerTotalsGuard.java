package example.claimshub.payment;

/**
 * Port of Pipelines/Components/TrailerTotalsComponent.cs (Encode stage of VendorRemittanceSendPipeline): the
 * PAY count, debit and credit cent totals and the hash total in TRL must agree with the body, or the file is
 * not sent. Offsets are the schema's. A field that is not an integer fails the way long.Parse does.
 */
public final class TrailerTotalsGuard {

    private TrailerTotalsGuard() {
    }

    public static void check(String file) throws TrailerTotalsException {
        String field = "PAY.AmountCents";
        try {
            int count = 0;
            long debit = 0;
            long credit = 0;
            String trailer = null;
            for (String record : file.split("\r\n")) {
                if (record.startsWith("PAY")) {
                    count++;
                    long cents = Long.parseLong(record.substring(57, 69));
                    if (record.charAt(69) == 'C') {
                        credit += cents;
                    } else {
                        debit += cents;
                    }
                } else if (record.startsWith("TRL")) {
                    trailer = record;
                }
            }
            if (trailer == null) {
                throw new TrailerTotalsException("TrailerTotals: no TRL record", null);
            }
            field = "TRL.PaymentCount";
            mustEqual("PaymentCount", Long.parseLong(trailer.substring(3, 9)), count);
            field = "TRL.DebitTotalCents";
            mustEqual("DebitTotalCents", Long.parseLong(trailer.substring(9, 23)), debit);
            field = "TRL.CreditTotalCents";
            mustEqual("CreditTotalCents", Long.parseLong(trailer.substring(23, 37)), credit);
            field = "TRL.HashTotal";
            mustEqual("HashTotal", Long.parseLong(trailer.substring(37, 47)), (debit + credit) % 10_000_000_000L);
        } catch (NumberFormatException | StringIndexOutOfBoundsException e) {
            throw new TrailerTotalsException("TrailerTotals: " + field + " is not an integer (" + e.getMessage() + ")", e);
        }
    }

    private static void mustEqual(String field, long trailer, long body) throws TrailerTotalsException {
        if (trailer != body) {
            throw new TrailerTotalsException("TrailerTotals: " + field + " in TRL is " + trailer + ", body gives " + body, null);
        }
    }
}
