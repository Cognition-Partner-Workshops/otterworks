package com.otterworks.report.preview;

import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Maps preview authorization failures to a small forbidden response.
 */
@RestControllerAdvice(assignableTypes = PreviewController.class)
public class PreviewExceptionHandler {

    @ExceptionHandler(PreviewDeniedException.class)
    public ResponseEntity<Map<String, String>> denied(PreviewDeniedException e) {
        Map<String, String> body = new LinkedHashMap<String, String>();
        body.put("error", e.getMessage());
        return ResponseEntity.status(HttpStatus.FORBIDDEN).contentType(MediaType.APPLICATION_JSON).body(body);
    }
}
