package com.otterworks.legacyportal.lambda.announcements;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.time.Instant;

import org.junit.jupiter.api.Test;

import software.amazon.awssdk.services.eventbridge.model.PutEventsRequestEntry;

class EventBridgeAnnouncementEventsTest {

    @Test
    void entryCarriesBusSourceDetailTypeAndDetail() {
        Announcement a = new Announcement("Release", "v1 is out", true);
        a.setId(7L);
        a.setCreatedAt(Instant.parse("2026-10-06T09:00:00.123456Z"));

        EventBridgeAnnouncementEvents events =
                new EventBridgeAnnouncementEvents(null, "otterworks-lp-ann-20261006-a1", "otterworks.legacy-portal.announcements");
        PutEventsRequestEntry entry = events.request(a).entries().get(0);

        assertEquals("otterworks-lp-ann-20261006-a1", entry.eventBusName());
        assertEquals("otterworks.legacy-portal.announcements", entry.source());
        assertEquals("AnnouncementCreated", entry.detailType());
        assertEquals("{\"id\":7,\"title\":\"Release\",\"published\":true,\"createdAt\":\"2026-10-06T09:00:00.123456Z\"}",
                entry.detail());
    }
}
