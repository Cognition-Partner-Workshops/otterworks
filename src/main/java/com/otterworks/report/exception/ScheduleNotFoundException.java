package com.otterworks.report.exception;

public class ScheduleNotFoundException extends RuntimeException {

    public ScheduleNotFoundException(Long id) {
        super("Report schedule " + id + " not found");
    }
}
