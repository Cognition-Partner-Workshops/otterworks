package com.otterworks.legacyportal.lambda.announcements;

import java.time.Duration;
import java.util.Set;
import java.util.concurrent.ThreadLocalRandom;
import java.util.function.Consumer;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import software.amazon.awssdk.core.client.config.ClientOverrideConfiguration;
import software.amazon.awssdk.services.eventbridge.EventBridgeClient;
import software.amazon.awssdk.services.eventbridge.model.PutEventsRequestEntry;
import software.amazon.awssdk.services.eventbridge.model.PutEventsResponse;
import software.amazon.awssdk.services.eventbridge.model.PutEventsResultEntry;

/**
 * Puts one {@code announcement.published} event on the run's custom bus per write. A failed put
 * never fails the request, so the HTTP response stays the one the Java monolith gave. Entries
 * EventBridge rejects with a transient error code are resubmitted a bounded number of times;
 * an event that still is not accepted is written to the log as an {@value #UNDELIVERED_MARKER}
 * line carrying the full entry, so it can be alarmed on and replayed with PutEvents.
 */
public class EventBridgeAnnouncementEvents implements AnnouncementEvents {

    public static final String SOURCE = "otterworks.legacy-portal";
    public static final String DETAIL_TYPE = "announcement.published";
    public static final String UNDELIVERED_MARKER = "ANNOUNCEMENT_EVENT_UNDELIVERED";

    static final int MAX_ATTEMPTS = 3;
    static final long BASE_DELAY_MILLIS = 100;
    static final long MAX_DELAY_MILLIS = 1_000;
    static final Duration API_CALL_TIMEOUT = Duration.ofSeconds(3);
    static final Set<String> RETRYABLE_ENTRY_ERRORS = Set.of("InternalFailure", "ThrottlingException");

    private static final ObjectMapper MAPPER = new ObjectMapper();

    interface Sleeper {
        void sleep(long millis) throws InterruptedException;
    }

    private final EventBridgeClient client;
    private final String busName;
    private final Sleeper sleeper;
    private final Consumer<String> log;

    public EventBridgeAnnouncementEvents(EventBridgeClient client, String busName) {
        this(client, busName, Thread::sleep, System.err::println);
    }

    EventBridgeAnnouncementEvents(EventBridgeClient client, String busName, Sleeper sleeper,
            Consumer<String> log) {
        this.client = client;
        this.busName = busName;
        this.sleeper = sleeper;
        this.log = log;
    }

    /** Bus from EVENT_BUS_NAME; no events when the variable is unset. */
    public static AnnouncementEvents fromEnvironment() {
        String bus = System.getenv("EVENT_BUS_NAME");
        if (bus == null || bus.isBlank()) {
            return NONE;
        }
        return new EventBridgeAnnouncementEvents(
                EventBridgeClient.builder().overrideConfiguration(clientOverrides()).build(), bus);
    }

    /**
     * Total deadline for one PutEvents call including the SDK's own retries. No per-attempt
     * timeout: the SDK retries attempt timeouts, which could put the same event twice.
     */
    static ClientOverrideConfiguration clientOverrides() {
        return ClientOverrideConfiguration.builder().apiCallTimeout(API_CALL_TIMEOUT).build();
    }

    public static String detail(Announcement a) {
        ObjectNode b = MAPPER.createObjectNode();
        b.put("id", a.getId());
        b.put("title", a.getTitle());
        b.put("body", a.getBody());
        b.put("published", a.isPublished());
        b.put("createdAt", a.getCreatedAt() == null ? null : a.getCreatedAt().toString());
        return b.toString();
    }

    @Override
    public void published(Announcement announcement) {
        PutEventsRequestEntry entry = PutEventsRequestEntry.builder()
                .eventBusName(busName)
                .source(SOURCE)
                .detailType(DETAIL_TYPE)
                .detail(detail(announcement))
                .build();
        String reason;
        int attempt = 0;
        while (true) {
            attempt++;
            try {
                PutEventsResponse response = client.putEvents(r -> r.entries(entry));
                if (response.failedEntryCount() == null || response.failedEntryCount() == 0) {
                    return;
                }
                PutEventsResultEntry result = response.entries().isEmpty() ? null : response.entries().get(0);
                String code = result == null ? null : result.errorCode();
                reason = "entry rejected: " + code + (result == null ? "" : " " + result.errorMessage());
                if (!RETRYABLE_ENTRY_ERRORS.contains(code) || attempt >= MAX_ATTEMPTS) {
                    break;
                }
            } catch (RuntimeException e) {
                // The SDK has already retried what it considers retryable within API_CALL_TIMEOUT.
                reason = "put failed: " + e;
                break;
            }
            try {
                sleeper.sleep(backoffMillis(attempt));
            } catch (InterruptedException ie) {
                Thread.currentThread().interrupt();
                reason = reason + " (interrupted)";
                break;
            }
        }
        undelivered(announcement, entry, attempt, reason);
    }

    /** Capped exponential backoff with full jitter. */
    static long backoffMillis(int attempt) {
        long ceiling = Math.min(MAX_DELAY_MILLIS, BASE_DELAY_MILLIS << Math.min(attempt - 1, 20));
        return ThreadLocalRandom.current().nextLong(ceiling + 1);
    }

    private void undelivered(Announcement announcement, PutEventsRequestEntry entry, int attempts,
            String reason) {
        ObjectNode line = MAPPER.createObjectNode();
        line.put("announcementId", announcement.getId());
        line.put("attempts", attempts);
        line.put("reason", reason);
        line.put("eventBusName", entry.eventBusName());
        line.put("source", entry.source());
        line.put("detailType", entry.detailType());
        line.put("detail", entry.detail());
        log.accept(UNDELIVERED_MARKER + " " + line);
    }
}
