package com.otterworks.legacyportal.lambda.announcements;

import java.util.List;
import java.util.NoSuchElementException;

public class AnnouncementService {

    private final AnnouncementRepository repository;
    private final AnnouncementEvents events;

    public AnnouncementService(AnnouncementRepository repository) {
        this(repository, AnnouncementEvents.NONE);
    }

    public AnnouncementService(AnnouncementRepository repository, AnnouncementEvents events) {
        this.repository = repository;
        this.events = events;
    }

    public Announcement create(String title, String body, boolean published) {
        Announcement saved = repository.save(new Announcement(title, body, published));
        events.published(saved);
        return saved;
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
        Announcement announcement = get(id);
        announcement.setPublished(true);
        Announcement saved = repository.save(announcement);
        events.published(saved);
        return saved;
    }
}
