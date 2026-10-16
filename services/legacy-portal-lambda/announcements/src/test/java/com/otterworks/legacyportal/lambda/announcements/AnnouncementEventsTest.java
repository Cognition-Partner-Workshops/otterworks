package com.otterworks.legacyportal.lambda.announcements;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

import org.junit.jupiter.api.Test;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

class AnnouncementEventsTest {

    static class Repo implements AnnouncementRepository {
        final List<Announcement> rows = new ArrayList<>();
        long next = 1;

        @Override
        public Announcement save(Announcement a) {
            if (a.getId() == null) {
                a.setId(next++);
                rows.add(a);
            }
            return a;
        }

        @Override
        public List<Announcement> findByPublishedTrueOrderByCreatedAtDesc() {
            return rows.stream().filter(Announcement::isPublished).toList();
        }

        @Override
        public List<Announcement> findAll() {
            return rows;
        }

        @Override
        public Optional<Announcement> findById(Long id) {
            return rows.stream().filter(a -> a.getId().equals(id)).findFirst();
        }
    }

    @Test
    void createAndPublishEachEmitTheSavedRow() {
        Repo repo = new Repo();
        List<Announcement> seen = new ArrayList<>();
        AnnouncementService service = new AnnouncementService(repo, a -> {
            assertTrue(repo.rows.contains(a), "event must follow the database write");
            seen.add(a);
        });

        Announcement draft = service.create("Maintenance", "Sunday 02:00", false);
        service.publish(draft.getId());
        service.listAll();
        service.listPublished();

        assertEquals(2, seen.size());
        assertEquals(1L, seen.get(0).getId());
        assertTrue(seen.get(1).isPublished());
    }

    @Test
    void detailCarriesTheAnnouncement() throws Exception {
        Announcement a = new Announcement("Title", "Body", true);
        a.setId(7L);
        a.setCreatedAt(Instant.parse("2026-10-06T08:00:00.123456Z"));

        JsonNode d = new ObjectMapper().readTree(EventBridgeAnnouncementEvents.detail(a));

        assertEquals(7, d.get("id").asLong());
        assertEquals("Title", d.get("title").asText());
        assertEquals("Body", d.get("body").asText());
        assertTrue(d.get("published").asBoolean());
        assertEquals("2026-10-06T08:00:00.123456Z", d.get("createdAt").asText());
    }
}
