package com.otterworks.report.util;

import com.google.common.util.concurrent.UncheckedExecutionException;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.web.client.ResourceAccessException;

import java.net.UnknownHostException;

import static org.junit.jupiter.api.Assertions.assertEquals;

class LegacyExceptionMessagesTest {

    private static final String AUDIT_REQUEST =
            "I/O error on GET request for \"http://audit-service:8090/api/v1/audit/events\": audit-service";

    @Test
    void restoresSpringFiveMessageThroughGuavaWrapper() {
        ResourceAccessException cause =
                new ResourceAccessException(AUDIT_REQUEST, new UnknownHostException("audit-service"));
        UncheckedExecutionException exception = new UncheckedExecutionException(cause);

        assertEquals(
                "org.springframework.web.client.ResourceAccessException: " + AUDIT_REQUEST
                        + "; nested exception is java.net.UnknownHostException: audit-service",
                LegacyExceptionMessages.message(exception));
    }

    @Test
    void appendsNestedCauseToSpringExceptionMessage() {
        ResourceAccessException exception =
                new ResourceAccessException(AUDIT_REQUEST, new UnknownHostException("audit-service"));

        assertEquals(
                AUDIT_REQUEST + "; nested exception is java.net.UnknownHostException: audit-service",
                LegacyExceptionMessages.message(exception));
    }

    @Test
    void preservesNestedMessagesAcrossSpringExceptionLevels() {
        DataAccessResourceFailureException exception = new DataAccessResourceFailureException(
                "outer", new ResourceAccessException("inner", new UnknownHostException("h")));

        assertEquals(
                "outer; nested exception is org.springframework.web.client.ResourceAccessException: inner"
                        + "; nested exception is java.net.UnknownHostException: h",
                LegacyExceptionMessages.message(exception));
    }

    @Test
    void includesCauseWhenSpringExceptionMessageIsNull() {
        ResourceAccessException exception = new ResourceAccessException(null, new UnknownHostException("h"));

        assertEquals("nested exception is java.net.UnknownHostException: h",
                LegacyExceptionMessages.message(exception));
    }

    @Test
    void leavesNonSpringExceptionMessagesUnchanged() {
        assertEquals("x", LegacyExceptionMessages.message(new IllegalStateException("x", new RuntimeException("y"))));
        assertEquals("x", LegacyExceptionMessages.message(new IllegalStateException("x")));
        assertEquals(null, LegacyExceptionMessages.message(null));
    }
}
