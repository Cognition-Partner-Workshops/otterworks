using OtterWorks.LegacyPortal.Announcements.Models;

namespace OtterWorks.LegacyPortal.Announcements.Services;

public interface IAnnouncementService
{
    Task<Announcement> CreateAsync(string title, string body, bool published, CancellationToken cancellationToken);

    Task<IReadOnlyList<Announcement>> ListPublishedAsync(CancellationToken cancellationToken);

    Task<IReadOnlyList<Announcement>> ListAllAsync(CancellationToken cancellationToken);

    /// <exception cref="Common.PortalNotFoundException">No announcement with this id.</exception>
    Task<Announcement> GetAsync(long id, CancellationToken cancellationToken);

    /// <exception cref="Common.PortalNotFoundException">No announcement with this id.</exception>
    Task<Announcement> PublishAsync(long id, CancellationToken cancellationToken);
}
