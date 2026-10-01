using Moq;
using OtterWorks.LegacyPortal.Common;
using OtterWorks.LegacyPortal.Feedback.Data;
using OtterWorks.LegacyPortal.Feedback.Models;
using OtterWorks.LegacyPortal.Feedback.Services;

namespace OtterWorks.LegacyPortal.Tests.Unit.Feedback;

public class FeedbackServiceTests
{
    private static readonly DateTimeOffset Now = new(2026, 10, 1, 13, 5, 13, TimeSpan.Zero);

    private readonly Mock<IFeedbackRepository> _repository = new(MockBehavior.Strict);
    private readonly Mock<TimeProvider> _timeProvider = new();
    private readonly FeedbackService _service;

    public FeedbackServiceTests()
    {
        _timeProvider.Setup(t => t.GetUtcNow()).Returns(Now.AddTicks(4_974_729));
        _service = new FeedbackService(_repository.Object, _timeProvider.Object);
    }

    [Theory]
    [InlineData(1)]
    [InlineData(3)]
    [InlineData(5)]
    public async Task SubmitAsync_saves_entry_with_microsecond_utc_timestamp(int rating)
    {
        FeedbackEntry? saved = null;
        _repository
            .Setup(r => r.SaveAsync(It.IsAny<FeedbackEntry>(), It.IsAny<CancellationToken>()))
            .Callback<FeedbackEntry, CancellationToken>((e, _) =>
            {
                e.Id = 42;
                saved = e;
            })
            .ReturnsAsync((FeedbackEntry e, CancellationToken _) => e);

        var result = await _service.SubmitAsync("u1", rating, "great");

        result.Should().BeSameAs(saved);
        result.Id.Should().Be(42);
        result.UserId.Should().Be("u1");
        result.Rating.Should().Be(rating);
        result.Message.Should().Be("great");
        result.CreatedAt.Kind.Should().Be(DateTimeKind.Utc);
        result.CreatedAt.Should().Be(Now.UtcDateTime.AddTicks(4_974_720));
        _repository.Verify(r => r.SaveAsync(It.IsAny<FeedbackEntry>(), It.IsAny<CancellationToken>()), Times.Once);
    }

    [Theory]
    [InlineData(0)]
    [InlineData(6)]
    [InlineData(-1)]
    [InlineData(int.MinValue)]
    [InlineData(int.MaxValue)]
    public async Task SubmitAsync_rejects_out_of_range_rating_without_saving(int rating)
    {
        var act = () => _service.SubmitAsync("u1", rating, "x");

        await act.Should().ThrowAsync<PortalValidationException>().WithMessage("rating must be between 1 and 5");
        _repository.VerifyNoOtherCalls();
    }

    [Fact]
    public async Task ListForUserAsync_delegates_to_ordered_repository_query()
    {
        var entries = new List<FeedbackEntry> { new("u1", 3, "ok", Now.UtcDateTime) };
        _repository
            .Setup(r => r.FindByUserIdOrderByCreatedAtDescAsync("u1", It.IsAny<CancellationToken>()))
            .ReturnsAsync(entries);

        var result = await _service.ListForUserAsync("u1");

        result.Should().BeSameAs(entries);
    }

    [Fact]
    public async Task ListForUserAsync_passes_empty_user_id_through()
    {
        _repository
            .Setup(r => r.FindByUserIdOrderByCreatedAtDescAsync(string.Empty, It.IsAny<CancellationToken>()))
            .ReturnsAsync([]);

        var result = await _service.ListForUserAsync(string.Empty);

        result.Should().BeEmpty();
    }

    [Fact]
    public async Task AverageRatingAsync_returns_zero_when_no_feedback()
    {
        _repository.Setup(r => r.FindAllAsync(It.IsAny<CancellationToken>())).ReturnsAsync([]);

        var result = await _service.AverageRatingAsync();

        result.Should().Be(0.0);
    }

    [Theory]
    [InlineData(new[] { 4, 2 }, 3.0)]
    [InlineData(new[] { 5 }, 5.0)]
    [InlineData(new[] { 5, 3, 1, 4, 2, 4 }, 3.1666666666666665)]
    [InlineData(new[] { 1, 2 }, 1.5)]
    public async Task AverageRatingAsync_matches_java_double_division(int[] ratings, double expected)
    {
        var entries = ratings.Select(r => new FeedbackEntry("u", r, "m", Now.UtcDateTime)).ToList();
        _repository.Setup(r => r.FindAllAsync(It.IsAny<CancellationToken>())).ReturnsAsync(entries);

        var result = await _service.AverageRatingAsync();

        result.Should().Be(expected);
    }

    [Fact]
    public void FeedbackResponse_FromEntity_copies_every_field()
    {
        var entry = new FeedbackEntry("u9", 4, "hello", Now.UtcDateTime) { Id = 7 };

        var response = FeedbackResponse.FromEntity(entry);

        response.Should().Be(new FeedbackResponse(7, "u9", 4, "hello", Now.UtcDateTime));
    }

    [Fact]
    public void Rating_bounds_match_java_constants()
    {
        FeedbackService.MinRating.Should().Be(1);
        FeedbackService.MaxRating.Should().Be(5);
    }
}
