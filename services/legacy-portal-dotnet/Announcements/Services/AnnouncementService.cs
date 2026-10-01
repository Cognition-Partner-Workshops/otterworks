using System.Globalization;
using OtterWorks.LegacyPortal.Announcements.Data;
using OtterWorks.LegacyPortal.Announcements.Models;
using OtterWorks.LegacyPortal.Common;

namespace OtterWorks.LegacyPortal.Announcements.Services;

public sealed class AnnouncementService : IAnnouncementService
{
    private readonly IAnnouncementRepository _repository;
    private readonly TimeProvider _timeProvider;

    public AnnouncementService(IAnnouncementRepository repository, TimeProvider timeProvider)
    {
        _repository = repository;
        _timeProvider = timeProvider;
    }

    public Task<Announcement> CreateAsync(string title, string body, bool published, CancellationToken cancellationToken)
    {
        var announcement = new Announcement(title, body, published, PortalClock.UtcNow(_timeProvider));
        return _repository.SaveAsync(announcement, cancellationToken);
    }

    public Task<IReadOnlyList<Announcement>> ListPublishedAsync(CancellationToken cancellationToken)
    {
        return _repository.FindByPublishedTrueOrderByCreatedAtDescAsync(cancellationToken);
    }

    public Task<IReadOnlyList<Announcement>> ListAllAsync(CancellationToken cancellationToken)
    {
        return _repository.FindAllAsync(cancellationToken);
    }

    public async Task<Announcement> GetAsync(long id, CancellationToken cancellationToken)
    {
        return await _repository.FindByIdAsync(id, cancellationToken)
            ?? throw new PortalNotFoundException(
                string.Create(CultureInfo.InvariantCulture, $"announcement {id} not found"));
    }

    public async Task<Announcement> PublishAsync(long id, CancellationToken cancellationToken)
    {
        var announcement = await GetAsync(id, cancellationToken);
        announcement.Published = true;
        return await _repository.SaveAsync(announcement, cancellationToken);
    }
}
