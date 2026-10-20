package example.claimshub.maps;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

/** The C# scripting functoids of InsertClaim_to_TriageFacts and Payment_to_LedgerPost, at their edges. */
class CSharpFunctoidPortTest {

    @Test
    void reserveRoundsMidpointsHalfToEven() {
        assertEquals("1253.12", InsertClaimToTriageFactsTransformer.computeReserve("1002.50", "THFT", "false"));
        assertEquals("2876.72", InsertClaimToTriageFactsTransformer.computeReserve("2501.50", "WIND", "false"));
        assertEquals("0.02", InsertClaimToTriageFactsTransformer.computeReserve("0.015", "COMP", "false"));
    }

    @Test
    void reserveAddsInjuryLoadingAndDefaultsUnknownCause() {
        assertEquals("1450.00", InsertClaimToTriageFactsTransformer.computeReserve("1000.00", "COLL", "true"));
        assertEquals("1000.00", InsertClaimToTriageFactsTransformer.computeReserve("1000.00", "TOWG", "false"));
        assertEquals("1100.00", InsertClaimToTriageFactsTransformer.computeReserve("1000.00", "COLL", "True"));
    }

    @Test
    void daysBetweenIsSignedWholeDays() {
        assertEquals("33", InsertClaimToTriageFactsTransformer.daysBetween("2026-08-10", "2026-09-12"));
        assertEquals("-1", InsertClaimToTriageFactsTransformer.daysBetween("2026-09-02", "2026-09-01"));
        assertEquals("366", InsertClaimToTriageFactsTransformer.daysBetween("2028-01-01", "2029-01-01"));
    }

    @Test
    void vendorReferenceCarriesMod97CheckDigits() {
        assertEquals("CLM2026100405880107-76", PaymentToLedgerPostTransformer.makeVendorReference("PI-2026-880107", "CLM-2026-100405"));
        assertEquals("CLM2026100401880111-97", PaymentToLedgerPostTransformer.makeVendorReference("PI-2026-880111", "CLM-2026-100401"));
    }

    @Test
    void moneyIsBankersRoundedToCents() {
        assertEquals("1234.56", Money.format(Money.parse("1234.565")));
        assertEquals("1234.58", Money.format(Money.parse("1234.575")));
        assertEquals("-25000.00", Money.format(Money.parse("-25000")));
    }
}
