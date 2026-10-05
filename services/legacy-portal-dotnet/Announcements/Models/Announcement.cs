namespace OtterWorks.LegacyPortal.Announcements.Models;

/// <summary>Row of <c>announcements.announcement</c>. <see cref="CreatedAt"/> is set once and never updated.</summary>
public class Announcement
{
    public Announcement(string title, string body, bool published, DateTime createdAt)
    {
        Title = title;
        Body = body;
        Published = published;
        CreatedAt = createdAt;
    }

    public long Id { get; set; }

    public string Title { get; set; }

    public string Body { get; set; }

    public bool Published { get; set; }

    public DateTime CreatedAt { get; private set; }
}
