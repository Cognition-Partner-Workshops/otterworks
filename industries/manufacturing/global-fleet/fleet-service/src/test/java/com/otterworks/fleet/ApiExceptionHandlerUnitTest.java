package com.otterworks.fleet;

import com.otterworks.fleet.api.ApiError;
import com.otterworks.fleet.api.ApiExceptionHandler;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertFalse;

class ApiExceptionHandlerUnitTest {

    @Test
    void genericExceptionReturnsSanitizedInternalError() {
        ResponseEntity<ApiError> response =
                new ApiExceptionHandler().handleException(new RuntimeException("SELECT secret FROM x"));

        assertEquals(HttpStatus.INTERNAL_SERVER_ERROR, response.getStatusCode());
        assertNotNull(response.getBody());
        assertEquals("INTERNAL_ERROR", response.getBody().code());
        assertEquals("Internal server error", response.getBody().message());
        assertFalse(response.getBody().message().contains("secret"));
    }
}
