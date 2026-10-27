package com.otterworks.fleet.eligibility;

public class InvalidPeriodException extends RuntimeException {

    public InvalidPeriodException() {
        super("Period must use YYYYMM format");
    }
}
