package com.otterworks.legacyportal.lambda.announcements;

import java.util.List;
import java.util.Optional;

public interface AnnouncementRepository {
    Announcement save(Announcement announcement);

    Announcement insert(Announcement announcement);

    Optional<Announcement> findById(Long id);

    List<Announcement> findAll();

    List<Announcement> findByPublishedTrueOrderByCreatedAtDesc();

    Announcement updatePublished(Long id, boolean published);
}
