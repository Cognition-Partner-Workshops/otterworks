package com.otterworks.report.service;

import com.google.common.util.concurrent.UncheckedExecutionException;
import org.junit.Test;
import org.springframework.web.client.ResourceAccessException;

import java.net.UnknownHostException;

import static org.junit.Assert.assertEquals;

public class ReportGenerationWorkerTest {

    @Test
    public void legacyMessageKeepsNestedExceptionSuffix() {
        ResourceAccessException e = new ResourceAccessException("I/O error on GET request: analytics-service",
                new UnknownHostException("analytics-service"));
        assertEquals("I/O error on GET request: analytics-service; nested exception is "
                + "java.net.UnknownHostException: analytics-service", ReportGenerationWorker.legacyMessage(e));
    }

    @Test
    public void legacyMessageRebuildsWrapperMessageFromCause() {
        UncheckedExecutionException e = new UncheckedExecutionException(new ResourceAccessException(
                "I/O error: analytics-service", new UnknownHostException("analytics-service")));
        assertEquals("org.springframework.web.client.ResourceAccessException: I/O error: analytics-service; "
                + "nested exception is java.net.UnknownHostException: analytics-service",
                ReportGenerationWorker.legacyMessage(e));
    }

    @Test
    public void legacyMessageLeavesOtherExceptionsAlone() {
        assertEquals("boom", ReportGenerationWorker.legacyMessage(
                new IllegalStateException("boom", new RuntimeException("cause"))));
    }
}
