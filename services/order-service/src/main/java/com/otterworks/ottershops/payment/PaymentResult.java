package com.otterworks.ottershops.payment;

public record PaymentResult(Status status, String reference, String cardBrand, String last4, String message) {
    public enum Status { APPROVED, DECLINED, INVALID }

    public boolean approved() {
        return status == Status.APPROVED;
    }
}
