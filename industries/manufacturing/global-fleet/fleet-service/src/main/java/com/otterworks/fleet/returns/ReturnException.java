package com.otterworks.fleet.returns;

import org.springframework.http.HttpStatus;

public class ReturnException extends RuntimeException {

    private final String code;
    private final HttpStatus status;

    public ReturnException(String code, String message, HttpStatus status) {
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
