package com.otterworks.fleet.eligibility;

public class EligibilityException extends RuntimeException {

    private final EligibilityReason reason;

    public EligibilityException(EligibilityReason reason) {
        super(reason.name());
        this.reason = reason;
    }

    public EligibilityException(EligibilityReason reason, String message) {
        super(message);
        this.reason = reason;
    }

    public EligibilityReason getReason() {
        return reason;
    }
}
