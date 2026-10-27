package com.otterworks.fleet.mileage;

public class MileageException extends RuntimeException {

    private final MileageReason reason;

    public MileageException(MileageReason reason) {
        super(reason.name());
        this.reason = reason;
    }

    public MileageReason getReason() {
        return reason;
    }
}
