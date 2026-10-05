package com.otterworks.legacyportal.lambda.announcements;

import java.util.List;
import java.util.NoSuchElementException;

public class AnnouncementService {

    private final AnnouncementRepository repository;

    public AnnouncementService(AnnouncementRepository repository) {
        this.repository = repository;
    }

    public Announcement create(String title, String body, boolean published) {
        return repository.save(new Announcement(title, body, published));
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
        return repository.save(announcement);
    }
}
