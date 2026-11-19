package com.otterworks.legacyportal.announcements;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import java.util.NoSuchElementException;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.JdbcTemplate;

@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import(AnnouncementService.class)
class AnnouncementServiceTest {

    @Autowired private AnnouncementService service;
    @Autowired private JdbcTemplate jdbcTemplate;

    @Test
    void listPublishedReturnsOnlyPublishedNewestFirst() {
        service.create("draft", "not visible", false);
        Announcement first = service.create("first", "hello", true);
        Announcement second = service.create("second", "world", true);
        jdbcTemplate.update(
                "update announcements.announcement set created_at = ? where id = ?",
                Timestamp.from(Instant.parse("2026-01-01T00:00:00Z")),
                first.getId());
        jdbcTemplate.update(
                "update announcements.announcement set created_at = ? where id = ?",
                Timestamp.from(Instant.parse("2026-01-02T00:00:00Z")),
                second.getId());

        List<Announcement> published = service.listPublished();

        assertThat(published).extracting(Announcement::getTitle).containsExactly("second", "first");
    }

    @Test
    void publishFlipsDraftToPublished() {
        Announcement draft = service.create("draft", "body", false);
        assertThat(draft.isPublished()).isFalse();

        Announcement published = service.publish(draft.getId());

        assertThat(published.isPublished()).isTrue();
        assertThat(service.listPublished()).extracting(Announcement::getId).contains(draft.getId());
    }

    @Test
    void getUnknownIdThrows() {
        assertThatThrownBy(() -> service.get(999_999L))
                .isInstanceOf(NoSuchElementException.class);
    }
}
