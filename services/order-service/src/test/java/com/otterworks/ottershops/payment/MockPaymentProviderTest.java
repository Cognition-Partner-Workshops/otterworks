package com.otterworks.ottershops.payment;

import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;

class MockPaymentProviderTest {
    final MockPaymentProvider p = new MockPaymentProvider(Clock.fixed(Instant.parse("2026-11-27T00:00:00Z"), ZoneOffset.UTC));

    PaymentResult pay(String number, int month, int year, String cvc) {
        return p.authorize(new PaymentRequest(1000, "USD", number, month, year, cvc, "A", "k"));
    }

    @Test
    void approvesTestCard() {
        PaymentResult r = pay("4242 4242 4242 4242", 12, 2030, "123");
        assertEquals(PaymentResult.Status.APPROVED, r.status());
        assertEquals("4242", r.last4());
    }

    @Test
    void declinesDeclineCard() {
        assertEquals(PaymentResult.Status.DECLINED, pay("4000000000000002", 12, 2030, "123").status());
    }

    @Test
    void rejectsBadLuhnExpiredAndBadCvc() {
        assertEquals(PaymentResult.Status.INVALID, pay("4242424242424241", 12, 2030, "123").status());
        assertEquals(PaymentResult.Status.INVALID, pay("4242424242424242", 1, 2026, "123").status());
        assertEquals(PaymentResult.Status.INVALID, pay("4242424242424242", 12, 2030, "1").status());
    }

    @Test
    void requestToStringNeverShowsCardNumber() {
        assertFalse(new PaymentRequest(1, "USD", "4242424242424242", 1, 2030, "123", "A", "k").toString().contains("4242"));
    }

    @Test
    void identifiesNetworkFromBin() {
        assertEquals("Visa", MockPaymentProvider.brand("4242424242424242"));
        assertEquals("Mastercard", MockPaymentProvider.brand("5105105105105100"));
        assertEquals("Mastercard", MockPaymentProvider.brand("2223003122003222"));
        assertEquals("Amex", MockPaymentProvider.brand("378282246310005"));
        assertEquals("Discover", MockPaymentProvider.brand("6011111111111117"));
    }
}
