using Moq;
using OtterWorks.LegacyPortal.Announcements.Data;
using OtterWorks.LegacyPortal.Announcements.Models;
using OtterWorks.LegacyPortal.Announcements.Services;
using OtterWorks.LegacyPortal.Common;

namespace OtterWorks.LegacyPortal.Tests.Unit.Announcements;

public class AnnouncementServiceTests
{
    private static readonly DateTimeOffset Now = new DateTime(2026, 10, 1, 13, 5, 13, DateTimeKind.Utc).AddTicks(1_869_897);

    private readonly Mock<IAnnouncementRepository> _repository = new(MockBehavior.Strict);
    private readonly AnnouncementService _service;

    public AnnouncementServiceTests()
    {
        _service = new AnnouncementService(_repository.Object, new FixedTimeProvider(Now));
    }

    [Theory]
    [InlineData(true)]
    [InlineData(false)]
    public async Task Create_saves_new_announcement_stamped_with_microsecond_utc_now(bool published)
    {
        Announcement? saved = null;
        _repository.Setup(r => r.SaveAsync(It.IsAny<Announcement>(), It.IsAny<CancellationToken>()))
            .Callback<Announcement, CancellationToken>((a, _) => saved = a)
            .ReturnsAsync((Announcement a, CancellationToken _) => a);

        var result = await _service.CreateAsync("title", "body", published, CancellationToken.None);

        result.Should().BeSameAs(saved);
        result.Id.Should().Be(0);
        result.Title.Should().Be("title");
        result.Body.Should().Be("body");
        result.Published.Should().Be(published);
        result.CreatedAt.Should().Be(new DateTime(2026, 10, 1, 13, 5, 13, DateTimeKind.Utc).AddTicks(1_869_890));
        result.CreatedAt.Kind.Should().Be(DateTimeKind.Utc);
        _repository.Verify(r => r.SaveAsync(It.IsAny<Announcement>(), It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task ListPublished_delegates_to_ordered_published_query()
    {
        IReadOnlyList<Announcement> rows = [Row(2, true), Row(1, true)];
        _repository.Setup(r => r.FindByPublishedTrueOrderByCreatedAtDescAsync(It.IsAny<CancellationToken>())).ReturnsAsync(rows);

        var result = await _service.ListPublishedAsync(CancellationToken.None);

        result.Should().BeSameAs(rows);
        _repository.Verify(r => r.FindAllAsync(It.IsAny<CancellationToken>()), Times.Never);
    }

    [Fact]
    public async Task ListAll_delegates_to_unordered_find_all()
    {
        IReadOnlyList<Announcement> rows = [Row(1, true), Row(3, false), Row(2, true)];
        _repository.Setup(r => r.FindAllAsync(It.IsAny<CancellationToken>())).ReturnsAsync(rows);

        var result = await _service.ListAllAsync(CancellationToken.None);

        result.Should().BeSameAs(rows);
        _repository.Verify(r => r.FindByPublishedTrueOrderByCreatedAtDescAsync(It.IsAny<CancellationToken>()), Times.Never);
    }

    [Fact]
    public async Task Get_returns_existing_row()
    {
        var row = Row(7, false);
        _repository.Setup(r => r.FindByIdAsync(7, It.IsAny<CancellationToken>())).ReturnsAsync(row);

        (await _service.GetAsync(7, CancellationToken.None)).Should().BeSameAs(row);
    }

    [Theory]
    [InlineData(999_999L)]
    [InlineData(-5L)]
    [InlineData(long.MaxValue)]
    public async Task Get_unknown_id_throws_not_found_with_java_message(long id)
    {
        _repository.Setup(r => r.FindByIdAsync(id, It.IsAny<CancellationToken>())).ReturnsAsync((Announcement?)null);

        var act = () => _service.GetAsync(id, CancellationToken.None);

        (await act.Should().ThrowAsync<PortalNotFoundException>()).WithMessage($"announcement {id} not found");
    }

    [Fact]
    public async Task Publish_sets_published_saves_and_keeps_created_at()
    {
        var row = Row(3, false);
        var createdAt = row.CreatedAt;
        _repository.Setup(r => r.FindByIdAsync(3, It.IsAny<CancellationToken>())).ReturnsAsync(row);
        _repository.Setup(r => r.SaveAsync(row, It.IsAny<CancellationToken>())).ReturnsAsync(row);

        var result = await _service.PublishAsync(3, CancellationToken.None);

        result.Published.Should().BeTrue();
        result.CreatedAt.Should().Be(createdAt);
        _repository.Verify(r => r.SaveAsync(row, It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task Publish_already_published_row_still_saves()
    {
        var row = Row(4, true);
        _repository.Setup(r => r.FindByIdAsync(4, It.IsAny<CancellationToken>())).ReturnsAsync(row);
        _repository.Setup(r => r.SaveAsync(row, It.IsAny<CancellationToken>())).ReturnsAsync(row);

        (await _service.PublishAsync(4, CancellationToken.None)).Published.Should().BeTrue();
        _repository.Verify(r => r.SaveAsync(row, It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task Publish_unknown_id_throws_not_found_and_does_not_save()
    {
        _repository.Setup(r => r.FindByIdAsync(42, It.IsAny<CancellationToken>())).ReturnsAsync((Announcement?)null);

        var act = () => _service.PublishAsync(42, CancellationToken.None);

        (await act.Should().ThrowAsync<PortalNotFoundException>()).WithMessage("announcement 42 not found");
        _repository.Verify(r => r.SaveAsync(It.IsAny<Announcement>(), It.IsAny<CancellationToken>()), Times.Never);
    }

    private static Announcement Row(long id, bool published) =>
        new("t" + id, "b" + id, published, new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc).AddMinutes(id)) { Id = id };
}
