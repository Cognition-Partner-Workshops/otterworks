using System.Globalization;
using OtterWorks.LegacyPortal.Common;
using OtterWorks.LegacyPortal.Feedback.Data;
using OtterWorks.LegacyPortal.Feedback.Models;

namespace OtterWorks.LegacyPortal.Feedback.Services;

public interface IFeedbackService
{
    Task<FeedbackEntry> SubmitAsync(string userId, int rating, string message, CancellationToken cancellationToken = default);

    Task<IReadOnlyList<FeedbackEntry>> ListForUserAsync(string userId, CancellationToken cancellationToken = default);

    Task<double> AverageRatingAsync(CancellationToken cancellationToken = default);
}

/// <summary>Port of the Java <c>FeedbackService</c>.</summary>
public sealed class FeedbackService : IFeedbackService
{
    public const int MinRating = 1;
    public const int MaxRating = 5;

    private readonly IFeedbackRepository _repository;
    private readonly TimeProvider _timeProvider;

    public FeedbackService(IFeedbackRepository repository, TimeProvider timeProvider)
    {
        _repository = repository;
        _timeProvider = timeProvider;
    }

    public Task<FeedbackEntry> SubmitAsync(string userId, int rating, string message, CancellationToken cancellationToken = default)
    {
        if (rating < MinRating || rating > MaxRating)
        {
            throw new PortalValidationException(string.Create(
                CultureInfo.InvariantCulture, $"rating must be between {MinRating} and {MaxRating}"));
        }

        return _repository.SaveAsync(
            new FeedbackEntry(userId, rating, message, PortalClock.UtcNow(_timeProvider)), cancellationToken);
    }

    public Task<IReadOnlyList<FeedbackEntry>> ListForUserAsync(string userId, CancellationToken cancellationToken = default)
    {
        return _repository.FindByUserIdOrderByCreatedAtDescAsync(userId, cancellationToken);
    }

    public async Task<double> AverageRatingAsync(CancellationToken cancellationToken = default)
    {
        var all = await _repository.FindAllAsync(cancellationToken);
        if (all.Count == 0)
        {
            return 0.0;
        }

        // Java: IntStream.average() == (double) longSum / count
        long sum = 0;
        foreach (var entry in all)
        {
            sum += entry.Rating;
        }

        return (double)sum / all.Count;
    }
}
