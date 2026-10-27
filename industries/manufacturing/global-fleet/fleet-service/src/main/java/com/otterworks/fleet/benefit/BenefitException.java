package com.otterworks.fleet.benefit;

import org.springframework.http.HttpStatus;

public class BenefitException extends RuntimeException {

    private final String code;
    private final HttpStatus status;

    public BenefitException(String code, HttpStatus status) {
        super(code);
        this.code = code;
        this.status = status;
    }

    public BenefitException(String code, HttpStatus status, String message) {
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
