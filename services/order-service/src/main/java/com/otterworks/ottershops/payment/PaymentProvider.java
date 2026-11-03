package com.otterworks.ottershops.payment;

public interface PaymentProvider {
    String name();

    PaymentResult authorize(PaymentRequest req);
}
