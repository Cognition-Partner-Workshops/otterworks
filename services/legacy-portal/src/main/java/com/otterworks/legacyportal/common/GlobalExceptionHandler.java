package com.otterworks.legacyportal.common;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.NoSuchElementException;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.bind.annotation.ExceptionHandler;

@ControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(NoSuchElementException.class)
    public ResponseEntity<Map<String, String>> handleNotFound(NoSuchElementException ex) {
        return error(HttpStatus.NOT_FOUND, ex.getMessage());
    }

    @ExceptionHandler(PortalAuthException.class)
    public ResponseEntity<Map<String, String>> handleAuth(PortalAuthException ex) {
        ResponseEntity<Map<String, String>> response = error(ex.getStatus(), ex.getMessage());
        if (ex.getKind() == PortalAuthException.Kind.UNAUTHENTICATED) {
            return ResponseEntity.status(ex.getStatus())
                    .header(HttpHeaders.WWW_AUTHENTICATE, "Bearer")
                    .body(response.getBody());
        }
        return response;
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, String>> handleBadRequest(IllegalArgumentException ex) {
        return error(HttpStatus.BAD_REQUEST, ex.getMessage());
    }

    private ResponseEntity<Map<String, String>> error(HttpStatus status, String message) {
        Map<String, String> body = new LinkedHashMap<>();
        body.put("error", status.getReasonPhrase());
        body.put("message", message);
        return ResponseEntity.status(status).body(body);
    }
}
