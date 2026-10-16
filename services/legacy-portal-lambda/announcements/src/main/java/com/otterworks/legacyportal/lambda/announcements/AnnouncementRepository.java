package com.otterworks.legacyportal.lambda.announcements;

import java.util.List;
import java.util.Optional;

public interface AnnouncementRepository {

    Announcement save(Announcement announcement);

    List<Announcement> findByPublishedTrueOrderByCreatedAtDesc();

    List<Announcement> findAll();

    Optional<Announcement> findById(Long id);
}
