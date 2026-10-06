package com.otterworks.legacyportal.lambda.announcements;

/**
 * Outbound domain events of the announcements context. Publishing is best effort: a failure
 * is logged and never changes the HTTP response the monolith contract defines.
 */
public interface AnnouncementEvents {

    void created(Announcement announcement);

    AnnouncementEvents NONE = announcement -> {
    };
}
