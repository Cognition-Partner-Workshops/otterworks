package com.otterworks.legacyportal.lambda.announcements;

/**
 * Receives an announcement after the service has written it to the database.
 */
public interface AnnouncementEvents {

    AnnouncementEvents NONE = announcement -> {
    };

    void published(Announcement announcement);
}
