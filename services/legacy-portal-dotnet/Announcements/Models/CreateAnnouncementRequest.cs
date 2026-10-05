namespace OtterWorks.LegacyPortal.Announcements.Models;

public sealed class CreateAnnouncementRequest
{
    public string? Title { get; set; }

    public string? Body { get; set; }

    public bool Published { get; set; }
}
