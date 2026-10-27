package com.otterworks.fleet.assignment;

import org.springframework.http.HttpStatus;

public class AssignmentException extends RuntimeException {

    private final String code;
    private final HttpStatus status;

    public AssignmentException(String code) {
        this(code, code, HttpStatus.UNPROCESSABLE_ENTITY);
    }

    public AssignmentException(String code, String message) {
        this(code, message, HttpStatus.UNPROCESSABLE_ENTITY);
    }

    public AssignmentException(String code, String message, HttpStatus status) {
        super(message);
        this.code = code;
        this.status = status;
    }

    public String getCode() {
        return code;
    }

    public HttpStatus getStatus() {
        return status;
    }
}
