package com.otterworks.ottershops.common;

import java.util.Map;
import org.springframework.http.HttpStatus;

public class ApiException extends RuntimeException {
    private final HttpStatus status;
    private final String error;
    private final transient Map<String, Object> details;

    public ApiException(HttpStatus status, String error, String message) {
        this(status, error, message, null);
    }

    public ApiException(HttpStatus status, String error, String message, Map<String, Object> details) {
        super(message);
        this.status = status;
        this.error = error;
        this.details = details;
    }

    public HttpStatus status() { return status; }
    public String error() { return error; }
    public Map<String, Object> details() { return details; }

    public static ApiException badRequest(String error, String message) {
        return new ApiException(HttpStatus.BAD_REQUEST, error, message);
    }

    public static ApiException notFound(String what) {
        return new ApiException(HttpStatus.NOT_FOUND, "NOT_FOUND", what + " not found");
    }

    public static ApiException unauthorized() {
        return new ApiException(HttpStatus.UNAUTHORIZED, "UNAUTHORIZED", "Sign in to continue");
    }
}
