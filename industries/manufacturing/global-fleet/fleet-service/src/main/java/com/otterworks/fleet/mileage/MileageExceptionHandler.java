package com.otterworks.fleet.mileage;

import com.otterworks.fleet.api.ApiError;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
@Order(Ordered.HIGHEST_PRECEDENCE)
public class MileageExceptionHandler {

    @ExceptionHandler(MileageException.class)
    public ResponseEntity<ApiError> handleMileage(MileageException exception) {
        HttpStatus status = switch (exception.getReason()) {
            case CLAIM_NOT_FOUND -> HttpStatus.NOT_FOUND;
            case CLAIM_ALREADY_DECIDED -> HttpStatus.CONFLICT;
            case INVALID_PERIOD -> HttpStatus.BAD_REQUEST;
            default -> HttpStatus.UNPROCESSABLE_ENTITY;
        };
        return ResponseEntity.status(status)
                .body(new ApiError(exception.getReason().name(), exception.getMessage()));
    }
}
