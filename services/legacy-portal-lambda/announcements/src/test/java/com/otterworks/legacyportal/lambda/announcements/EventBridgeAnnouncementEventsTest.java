package com.otterworks.legacyportal.lambda.announcements;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;
import java.util.function.Supplier;

import org.junit.jupiter.api.Test;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import software.amazon.awssdk.core.client.config.ClientOverrideConfiguration;
import software.amazon.awssdk.core.exception.SdkClientException;
import software.amazon.awssdk.services.eventbridge.EventBridgeClient;
import software.amazon.awssdk.services.eventbridge.model.PutEventsRequest;
import software.amazon.awssdk.services.eventbridge.model.PutEventsResponse;
import software.amazon.awssdk.services.eventbridge.model.PutEventsResultEntry;

class EventBridgeAnnouncementEventsTest {

    static final class FakeEventBridge implements EventBridgeClient {
        final List<PutEventsRequest> requests = new ArrayList<>();
        final Deque<Supplier<PutEventsResponse>> steps = new ArrayDeque<>();

        FakeEventBridge then(Supplier<PutEventsResponse> step) {
            steps.add(step);
            return this;
        }

        @Override
        public PutEventsResponse putEvents(PutEventsRequest request) {
            requests.add(request);
            return (steps.size() > 1 ? steps.poll() : steps.peek()).get();
        }

        @Override
        public String serviceName() {
            return "events";
        }

        @Override
        public void close() {
        }
    }

    final List<Long> sleeps = new ArrayList<>();
    final List<String> logs = new ArrayList<>();

    EventBridgeAnnouncementEvents events(FakeEventBridge eb) {
        return new EventBridgeAnnouncementEvents(eb, "bus", sleeps::add, logs::add);
    }

    static PutEventsResponse failed(String code) {
        return PutEventsResponse.builder().failedEntryCount(1)
                .entries(PutEventsResultEntry.builder().errorCode(code).errorMessage(code).build()).build();
    }

    static PutEventsResponse accepted() {
        return PutEventsResponse.builder().failedEntryCount(0)
                .entries(PutEventsResultEntry.builder().eventId("e-1").build()).build();
    }

    static Announcement announcement() {
        Announcement a = new Announcement("Maintenance", "Sunday 02:00", true);
        a.setId(42L);
        a.setCreatedAt(Instant.parse("2026-10-06T08:00:00Z"));
        return a;
    }

    @Test
    void reproTransientEntryFailureIsResubmitted() {
        FakeEventBridge eb = new FakeEventBridge()
                .then(() -> failed("InternalFailure"))
                .then(EventBridgeAnnouncementEventsTest::accepted);

        events(eb).published(announcement());

        assertEquals(2, eb.requests.size(), "a per-entry InternalFailure must be resubmitted");
        assertEquals(eb.requests.get(0).entries(), eb.requests.get(1).entries());
        assertTrue(logs.isEmpty());
    }

    @Test
    void throttledEntryIsResubmittedABoundedNumberOfTimesThenCaptured() throws Exception {
        FakeEventBridge eb = new FakeEventBridge().then(() -> failed("ThrottlingException"));

        events(eb).published(announcement());

        assertEquals(EventBridgeAnnouncementEvents.MAX_ATTEMPTS, eb.requests.size());
        assertEquals(EventBridgeAnnouncementEvents.MAX_ATTEMPTS - 1, sleeps.size());
        assertTrue(sleeps.stream().allMatch(s -> s >= 0 && s <= EventBridgeAnnouncementEvents.MAX_DELAY_MILLIS));
        assertEquals(1, logs.size());
        assertTrue(logs.get(0).startsWith(EventBridgeAnnouncementEvents.UNDELIVERED_MARKER + " "));
        JsonNode line = new ObjectMapper().readTree(
                logs.get(0).substring(EventBridgeAnnouncementEvents.UNDELIVERED_MARKER.length() + 1));
        assertEquals(42, line.get("announcementId").asLong());
        assertEquals(3, line.get("attempts").asInt());
        assertEquals("bus", line.get("eventBusName").asText());
        assertEquals(EventBridgeAnnouncementEvents.SOURCE, line.get("source").asText());
        assertEquals(EventBridgeAnnouncementEvents.DETAIL_TYPE, line.get("detailType").asText());
        assertEquals(EventBridgeAnnouncementEvents.detail(announcement()), line.get("detail").asText(),
                "the captured line carries the full entry so it can be replayed");
    }

    @Test
    void permanentEntryErrorIsNotRetried() {
        FakeEventBridge eb = new FakeEventBridge().then(() -> failed("AccessDeniedException"));

        events(eb).published(announcement());

        assertEquals(1, eb.requests.size());
        assertTrue(sleeps.isEmpty());
        assertEquals(1, logs.size());
        assertTrue(logs.get(0).contains("AccessDeniedException"));
    }

    @Test
    void sdkFailureIsCapturedWithoutAnotherRetryLayerAndNeverFailsTheRequest() {
        FakeEventBridge eb = new FakeEventBridge().then(() -> {
            throw SdkClientException.create("Unable to execute HTTP request");
        });

        assertDoesNotThrow(() -> events(eb).published(announcement()));

        assertEquals(1, eb.requests.size(), "the SDK already retried; do not multiply its attempts");
        assertEquals(1, logs.size());
        assertTrue(logs.get(0).startsWith(EventBridgeAnnouncementEvents.UNDELIVERED_MARKER));
    }

    @Test
    void backoffIsJitteredAndCapped() {
        for (int attempt = 1; attempt <= 30; attempt++) {
            long d = EventBridgeAnnouncementEvents.backoffMillis(attempt);
            assertTrue(d >= 0 && d <= EventBridgeAnnouncementEvents.MAX_DELAY_MILLIS, "delay " + d);
        }
    }

    @Test
    void clientHasATotalDeadlineAndNoRetriedAttemptTimeout() {
        ClientOverrideConfiguration c = EventBridgeAnnouncementEvents.clientOverrides();
        assertEquals(Duration.ofSeconds(3), c.apiCallTimeout().orElseThrow());
        assertFalse(c.apiCallAttemptTimeout().isPresent());
    }
}
