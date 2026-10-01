using Microsoft.EntityFrameworkCore;
using OtterWorks.LegacyPortal.Announcements.Data;
using OtterWorks.LegacyPortal.Announcements.Models;
using OtterWorks.LegacyPortal.Announcements.Services;
using OtterWorks.LegacyPortal.Common;

namespace OtterWorks.LegacyPortal.Tests.Unit.Announcements;

/// <summary>Port of Java <c>AnnouncementServiceTest</c> (@DataJpaTest): real service + repository on EF InMemory.</summary>
public sealed class AnnouncementServiceJavaPortTests : IDisposable
{
    private readonly AnnouncementsDbContext _db;
    private readonly FixedTimeProvider _clock = new(new DateTimeOffset(2026, 10, 1, 12, 0, 0, TimeSpan.Zero));
    private readonly AnnouncementService _service;

    public AnnouncementServiceJavaPortTests()
    {
        var options = new DbContextOptionsBuilder<AnnouncementsDbContext>()
            .UseInMemoryDatabase($"announcements-{Guid.NewGuid():N}")
            .Options;
        _db = new AnnouncementsDbContext(options);
        _service = new AnnouncementService(new AnnouncementRepository(_db), _clock);
    }

    public void Dispose() => _db.Dispose();

    [Fact]
    public async Task ListPublishedReturnsOnlyPublishedNewestFirst()
    {
        await CreateAsync("draft", "not visible", false);
        await CreateAsync("first", "hello", true);
        await CreateAsync("second", "world", true);

        var published = await _service.ListPublishedAsync(CancellationToken.None);

        published.Select(a => a.Title).Should().Equal("second", "first");
    }

    [Fact]
    public async Task PublishFlipsDraftToPublished()
    {
        var draft = await CreateAsync("draft", "body", false);
        draft.Published.Should().BeFalse();

        var published = await _service.PublishAsync(draft.Id, CancellationToken.None);

        published.Published.Should().BeTrue();
        (await _service.ListPublishedAsync(CancellationToken.None)).Select(a => a.Id).Should().Contain(draft.Id);
    }

    [Fact]
    public async Task GetUnknownIdThrows()
    {
        var act = () => _service.GetAsync(999_999L, CancellationToken.None);

        await act.Should().ThrowAsync<PortalNotFoundException>();
    }

    [Fact]
    public async Task ListAllReturnsDraftsAndPublished()
    {
        await CreateAsync("draft", "d", false);
        await CreateAsync("live", "l", true);

        (await _service.ListAllAsync(CancellationToken.None)).Select(a => a.Title).Should().BeEquivalentTo("draft", "live");
    }

    [Fact]
    public async Task PublishDoesNotChangeCreatedAt()
    {
        var draft = await CreateAsync("draft", "body", false);
        var createdAt = draft.CreatedAt;
        _clock.Now = _clock.Now.AddHours(5);

        await _service.PublishAsync(draft.Id, CancellationToken.None);

        _db.ChangeTracker.Clear();
        (await _service.GetAsync(draft.Id, CancellationToken.None)).CreatedAt.Should().Be(createdAt);
    }

    private async Task<Announcement> CreateAsync(string title, string body, bool published)
    {
        var announcement = await _service.CreateAsync(title, body, published, CancellationToken.None);
        _clock.Now = _clock.Now.AddSeconds(1);
        return announcement;
    }
}
