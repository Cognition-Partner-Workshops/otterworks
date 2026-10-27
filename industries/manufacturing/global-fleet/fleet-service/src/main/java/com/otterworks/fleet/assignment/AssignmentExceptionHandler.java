package com.otterworks.fleet.assignment;

import com.otterworks.fleet.api.ApiError;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
@Order(Ordered.HIGHEST_PRECEDENCE)
public class AssignmentExceptionHandler {

    @ExceptionHandler(AssignmentException.class)
    public ResponseEntity<ApiError> handleAssignment(AssignmentException exception) {
        return ResponseEntity.status(exception.getStatus())
                .body(new ApiError(exception.getCode(), exception.getMessage()));
    }
}
