package com.otterworks.legacyportal.lambda.announcements;

import com.fasterxml.jackson.annotation.JsonPropertyOrder;
import java.time.Instant;

@JsonPropertyOrder({"id", "title", "body", "published", "createdAt"})
public final class Announcement {
    private final Long id;
    private final String title;
    private final String body;
    private final boolean published;
    private final Instant createdAt;

    public Announcement(Long id, String title, String body, boolean published, Instant createdAt) {
        this.id = id;
        this.title = title;
        this.body = body;
        this.published = published;
        this.createdAt = createdAt;
    }

    public Long getId() {
        return id;
    }

    public String getTitle() {
        return title;
    }

    public String getBody() {
        return body;
    }

    public boolean isPublished() {
        return published;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
