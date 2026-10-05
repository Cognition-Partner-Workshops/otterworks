using Microsoft.EntityFrameworkCore;
using OtterWorks.LegacyPortal.Common;
using OtterWorks.LegacyPortal.Feedback.Data;
using OtterWorks.LegacyPortal.Feedback.Services;

namespace OtterWorks.LegacyPortal.Tests.Unit.Feedback;

/// <summary>Port of the Java <c>FeedbackServiceTest</c> (@DataJpaTest: real repository, fresh database per test).</summary>
public sealed class FeedbackServiceJavaPortTests : IDisposable
{
    private readonly FeedbackDbContext _db;
    private readonly FeedbackService _service;

    public FeedbackServiceJavaPortTests()
    {
        var options = new DbContextOptionsBuilder<FeedbackDbContext>()
            .UseInMemoryDatabase($"feedback-java-port-{Guid.NewGuid():N}")
            .Options;
        _db = new FeedbackDbContext(options);
        _service = new FeedbackService(new FeedbackRepository(_db), TimeProvider.System);
    }

    public void Dispose() => _db.Dispose();

    [Fact]
    public async Task SubmitAndListForUser()
    {
        await _service.SubmitAsync("u1", 5, "great");
        await _service.SubmitAsync("u1", 3, "ok");
        await _service.SubmitAsync("u2", 1, "bad");

        (await _service.ListForUserAsync("u1")).Should().HaveCount(2);
        (await _service.ListForUserAsync("u2")).Should().HaveCount(1);
    }

    [Fact]
    public async Task AverageRatingAcrossAllFeedback()
    {
        await _service.SubmitAsync("u1", 4, "a");
        await _service.SubmitAsync("u2", 2, "b");

        (await _service.AverageRatingAsync()).Should().Be(3.0);
    }

    [Fact]
    public async Task RejectsOutOfRangeRating()
    {
        await _service.Invoking(s => s.SubmitAsync("u1", 6, "too high")).Should().ThrowAsync<PortalValidationException>();
        await _service.Invoking(s => s.SubmitAsync("u1", 0, "too low")).Should().ThrowAsync<PortalValidationException>();
    }

    [Fact]
    public async Task ListForUser_orders_newest_first()
    {
        var clock = new SteppingClock(new DateTimeOffset(2026, 10, 1, 13, 0, 0, TimeSpan.Zero));
        var service = new FeedbackService(new FeedbackRepository(_db), clock);
        var first = await service.SubmitAsync("u1", 5, "first");
        var second = await service.SubmitAsync("u1", 3, "second");
        var third = await service.SubmitAsync("u1", 1, "third");

        var listed = await service.ListForUserAsync("u1");

        listed.Select(e => e.Id).Should().Equal(third.Id, second.Id, first.Id);
        first.Id.Should().Be(1);
    }

    private sealed class SteppingClock : TimeProvider
    {
        private DateTimeOffset _now;

        public SteppingClock(DateTimeOffset start) => _now = start;

        public override DateTimeOffset GetUtcNow()
        {
            _now = _now.AddMilliseconds(1);
            return _now;
        }
    }
}
