package com.otterworks.legacyportal.lambda.announcements;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import software.amazon.awssdk.services.eventbridge.EventBridgeClient;
import software.amazon.awssdk.services.eventbridge.model.PutEventsRequestEntry;
import software.amazon.awssdk.services.eventbridge.model.PutEventsResponse;

/**
 * Puts one {@code announcement.published} event on the run's custom bus per write. A failed put
 * is logged and swallowed, so the HTTP response stays the one the Java monolith gave.
 */
public class EventBridgeAnnouncementEvents implements AnnouncementEvents {

    public static final String SOURCE = "otterworks.legacy-portal";
    public static final String DETAIL_TYPE = "announcement.published";

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private final EventBridgeClient client;
    private final String busName;

    public EventBridgeAnnouncementEvents(EventBridgeClient client, String busName) {
        this.client = client;
        this.busName = busName;
    }

    /** Bus from EVENT_BUS_NAME; no events when the variable is unset. */
    public static AnnouncementEvents fromEnvironment() {
        String bus = System.getenv("EVENT_BUS_NAME");
        if (bus == null || bus.isBlank()) {
            return NONE;
        }
        return new EventBridgeAnnouncementEvents(EventBridgeClient.builder().build(), bus);
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
        try {
            PutEventsResponse response = client.putEvents(r -> r.entries(PutEventsRequestEntry.builder()
                    .eventBusName(busName)
                    .source(SOURCE)
                    .detailType(DETAIL_TYPE)
                    .detail(detail(announcement))
                    .build()));
            if (response.failedEntryCount() != null && response.failedEntryCount() > 0) {
                System.err.println("announcement event not accepted for id " + announcement.getId()
                        + ": " + response.entries().get(0).errorCode());
            }
        } catch (RuntimeException e) {
            System.err.println("announcement event failed for id " + announcement.getId() + ": " + e);
        }
    }
}
