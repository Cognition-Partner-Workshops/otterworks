namespace OtterWorks.LegacyPortal.Feedback.Models;

public sealed class SubmitFeedbackRequest
{
    public string? UserId { get; set; }

    public int Rating { get; set; }

    public string? Message { get; set; }
}

public sealed record FeedbackResponse(long Id, string UserId, int Rating, string Message, DateTime CreatedAt)
{
    public static FeedbackResponse FromEntity(FeedbackEntry entry)
    {
        ArgumentNullException.ThrowIfNull(entry);
        return new FeedbackResponse(entry.Id, entry.UserId, entry.Rating, entry.Message, entry.CreatedAt);
    }
}

public sealed record AverageRatingResponse(double AverageRating);
