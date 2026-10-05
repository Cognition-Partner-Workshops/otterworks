package com.otterworks.legacyportal.lambda.announcements;

import java.time.Instant;
import java.util.List;
import java.util.NoSuchElementException;

public final class AnnouncementService {
    private final AnnouncementRepository repository;

    public AnnouncementService(AnnouncementRepository repository) {
        this.repository = repository;
    }

    public Announcement create(String title, String body, boolean published) {
        return repository.insert(new Announcement(null, title, body, published, Instant.now()));
    }

    public List<Announcement> listPublished() {
        return repository.findByPublishedTrueOrderByCreatedAtDesc();
    }

    public List<Announcement> listAll() {
        return repository.findAll();
    }

    public Announcement get(Long id) {
        return repository.findById(id)
                .orElseThrow(() -> new NoSuchElementException("announcement " + id + " not found"));
    }

    public Announcement publish(Long id) {
        get(id);
        return repository.updatePublished(id, true);
    }
}
