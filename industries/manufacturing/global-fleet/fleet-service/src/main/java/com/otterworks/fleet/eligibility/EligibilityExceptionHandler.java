package com.otterworks.fleet.eligibility;

import com.otterworks.fleet.api.ApiError;
import java.time.format.DateTimeParseException;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
@Order(Ordered.HIGHEST_PRECEDENCE)
public class EligibilityExceptionHandler {

    @ExceptionHandler(EligibilityException.class)
    public ResponseEntity<ApiError> handleEligibility(EligibilityException exception) {
        HttpStatus status = switch (exception.getReason()) {
            case EMPLOYEE_NUMBER_REQUIRED -> HttpStatus.BAD_REQUEST;
            case EMPLOYEE_NOT_FOUND -> HttpStatus.NOT_FOUND;
            default -> HttpStatus.UNPROCESSABLE_ENTITY;
        };
        return ResponseEntity.status(status)
                .body(new ApiError(exception.getReason().name(), exception.getMessage()));
    }

    @ExceptionHandler({InvalidPeriodException.class, DateTimeParseException.class})
    public ResponseEntity<ApiError> handleInvalidPeriod(RuntimeException exception) {
        return ResponseEntity.badRequest()
                .body(new ApiError("BAD_REQUEST", "Period must use YYYYMM format"));
    }
}
