package com.otterworks.ottershops.payment;

import java.time.Clock;
import java.time.YearMonth;
import java.util.UUID;

/**
 * Test-mode card processor. 4242 4242 4242 4242 approves, 4000 0000 0000 0002 declines, and any
 * number that fails the Luhn check, an expired date or a malformed CVC is rejected as invalid.
 */
public class MockPaymentProvider implements PaymentProvider {
    public static final String DECLINE_CARD = "4000000000000002";

    private final Clock clock;

    public MockPaymentProvider(Clock clock) {
        this.clock = clock;
    }

    @Override
    public String name() {
        return "mock";
    }

    @Override
    public PaymentResult authorize(PaymentRequest req) {
        String number = digits(req.cardNumber());
        String brand = brand(number);
        String last4 = number.length() >= 4 ? number.substring(number.length() - 4) : null;
        if (number.length() < 12 || number.length() > 19 || !luhn(number)) {
            return new PaymentResult(PaymentResult.Status.INVALID, null, brand, last4, "Check your card number");
        }
        if (req.expMonth() < 1 || req.expMonth() > 12) {
            return new PaymentResult(PaymentResult.Status.INVALID, null, brand, last4, "Check the expiry month");
        }
        int year = req.expYear() < 100 ? 2000 + req.expYear() : req.expYear();
        if (YearMonth.of(year, req.expMonth()).isBefore(YearMonth.now(clock))) {
            return new PaymentResult(PaymentResult.Status.INVALID, null, brand, last4, "This card has expired");
        }
        String cvc = req.cvc() == null ? "" : req.cvc().trim();
        if (!cvc.matches("\\d{3,4}")) {
            return new PaymentResult(PaymentResult.Status.INVALID, null, brand, last4, "Check the security code");
        }
        if (DECLINE_CARD.equals(number)) {
            return new PaymentResult(PaymentResult.Status.DECLINED, null, brand, last4, "Your card was declined. Try another card.");
        }
        return new PaymentResult(PaymentResult.Status.APPROVED, "mock_" + UUID.randomUUID(), brand, last4, "Approved");
    }

    static String digits(String s) {
        return s == null ? "" : s.replaceAll("\\D", "");
    }

    static boolean luhn(String number) {
        int sum = 0;
        boolean dbl = false;
        for (int i = number.length() - 1; i >= 0; i--) {
            int d = number.charAt(i) - '0';
            if (dbl) {
                d *= 2;
                if (d > 9) {
                    d -= 9;
                }
            }
            sum += d;
            dbl = !dbl;
        }
        return sum % 10 == 0;
    }

    static String brand(String n) {
        if (n.startsWith("4")) {
            return "Visa";
        }
        if (n.startsWith("34") || n.startsWith("37")) {
            return "Amex";
        }
        if (n.startsWith("6011") || n.startsWith("65")) {
            return "Discover";
        }
        if (n.length() >= 2) {
            int two = Integer.parseInt(n.substring(0, 2));
            if (two >= 51 && two <= 55) {
                return "Mastercard";
            }
        }
        if (n.length() >= 4) {
            int four = Integer.parseInt(n.substring(0, 4));
            if (four >= 2221 && four <= 2720) {
                return "Mastercard";
            }
        }
        return "Card";
    }
}
