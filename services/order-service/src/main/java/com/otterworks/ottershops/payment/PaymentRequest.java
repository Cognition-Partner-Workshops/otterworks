package com.otterworks.ottershops.payment;

public record PaymentRequest(
        long amountCents,
        String currency,
        String cardNumber,
        int expMonth,
        int expYear,
        String cvc,
        String name,
        String idempotencyKey) {

    @Override
    public String toString() {
        return "PaymentRequest[amountCents=" + amountCents + ", currency=" + currency + ", idempotencyKey=" + idempotencyKey + "]";
    }
}
