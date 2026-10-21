namespace OtterWorks.LegacyPortal.Announcements.Models;

public sealed record AnnouncementResponse(long Id, string Title, string Body, bool Published, DateTime CreatedAt)
{
    public static AnnouncementResponse FromEntity(Announcement announcement)
    {
        ArgumentNullException.ThrowIfNull(announcement);
        return new AnnouncementResponse(
            announcement.Id, announcement.Title, announcement.Body, announcement.Published, announcement.CreatedAt);
    }
}
