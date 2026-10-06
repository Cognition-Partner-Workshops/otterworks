package com.otterworks.legacyportal.lambda.announcements;

import java.util.LinkedHashMap;
import java.util.Map;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

import software.amazon.awssdk.services.eventbridge.EventBridgeClient;
import software.amazon.awssdk.services.eventbridge.model.PutEventsRequest;
import software.amazon.awssdk.services.eventbridge.model.PutEventsRequestEntry;
import software.amazon.awssdk.services.eventbridge.model.PutEventsResponse;
import software.amazon.awssdk.services.eventbridge.model.PutEventsResultEntry;

/**
 * Puts one {@code AnnouncementCreated} event on the run's custom event bus per created
 * announcement, so the notification side can subscribe instead of polling the table.
 */
public class EventBridgeAnnouncementEvents implements AnnouncementEvents {

    public static final String DETAIL_TYPE = "AnnouncementCreated";

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private final EventBridgeClient client;
    private final String eventBusName;
    private final String source;

    public EventBridgeAnnouncementEvents(EventBridgeClient client, String eventBusName, String source) {
        this.client = client;
        this.eventBusName = eventBusName;
        this.source = source;
    }

    @Override
    public void created(Announcement announcement) {
        try {
            PutEventsResponse response = client.putEvents(request(announcement));
            PutEventsResultEntry entry = response.entries().get(0);
            if (response.failedEntryCount() != null && response.failedEntryCount() > 0) {
                System.out.println("{\"level\":\"ERROR\",\"msg\":\"AnnouncementCreated rejected\",\"announcementId\":"
                        + announcement.getId() + ",\"errorCode\":\"" + entry.errorCode() + "\"}");
            } else {
                System.out.println("{\"level\":\"INFO\",\"msg\":\"AnnouncementCreated published\",\"announcementId\":"
                        + announcement.getId() + ",\"eventId\":\"" + entry.eventId() + "\",\"eventBus\":\""
                        + eventBusName + "\"}");
            }
        } catch (RuntimeException e) {
            System.out.println("{\"level\":\"ERROR\",\"msg\":\"AnnouncementCreated not published\",\"announcementId\":"
                    + announcement.getId() + ",\"error\":\"" + e.getClass().getSimpleName() + "\"}");
        }
    }

    PutEventsRequest request(Announcement announcement) {
        return PutEventsRequest.builder()
                .entries(PutEventsRequestEntry.builder()
                        .eventBusName(eventBusName)
                        .source(source)
                        .detailType(DETAIL_TYPE)
                        .detail(detail(announcement))
                        .build())
                .build();
    }

    static String detail(Announcement announcement) {
        Map<String, Object> detail = new LinkedHashMap<>();
        detail.put("id", announcement.getId());
        detail.put("title", announcement.getTitle());
        detail.put("published", announcement.isPublished());
        detail.put("createdAt", announcement.getCreatedAt() == null ? null : announcement.getCreatedAt().toString());
        try {
            return MAPPER.writeValueAsString(detail);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException(e);
        }
    }
}
