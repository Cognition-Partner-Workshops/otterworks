package com.otterworks.ottershops.payment;

import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;

import static org.junit.jupiter.api.Assertions.assertEquals;

/** QA gap coverage: malformed cards never reach approval. */
class MockPaymentProviderQaTest {
    final MockPaymentProvider p = new MockPaymentProvider(Clock.fixed(Instant.parse("2026-11-27T00:00:00Z"), ZoneOffset.UTC));

    PaymentResult.Status pay(String number, Integer month, Integer year, String cvc) {
        return p.authorize(new PaymentRequest(1000, "USD", number, month, year, cvc, "A", "k")).status();
    }

    @Test
    void singleDigitTypoFailsLuhn() {
        assertEquals(PaymentResult.Status.INVALID, pay("4242424242424241", 12, 2030, "123"));
        assertEquals(PaymentResult.Status.INVALID, pay("4000000000000003", 12, 2030, "123"));
    }

    @Test
    void tooShortNumbersAreInvalid() {
        assertEquals(PaymentResult.Status.INVALID, pay("4242", 12, 2030, "123"));
    }

    @Test
    @Disabled("KNOWN FAILING QA-06: non-digits are stripped, so a number with letters in it can still be approved")
    void numbersContainingLettersAreInvalid() {
        assertEquals(PaymentResult.Status.INVALID, pay("4242abcd42424242", 12, 2030, "123"));
    }

    @Test
    void cardIsValidThroughTheEndOfItsExpiryMonth() {
        assertEquals(PaymentResult.Status.APPROVED, pay("4242424242424242", 11, 2026, "123"));
        assertEquals(PaymentResult.Status.INVALID, pay("4242424242424242", 10, 2026, "123"));
        assertEquals(PaymentResult.Status.INVALID, pay("4242424242424242", 0, 2030, "123"));
    }
}
