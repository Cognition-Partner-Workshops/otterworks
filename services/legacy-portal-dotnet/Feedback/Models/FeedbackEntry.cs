namespace OtterWorks.LegacyPortal.Feedback.Models;

/// <summary>Row of <c>feedback.feedback</c> (Java entity <c>Feedback</c>).</summary>
public class FeedbackEntry
{
    public FeedbackEntry(string userId, int rating, string message, DateTime createdAt)
    {
        UserId = userId;
        Rating = rating;
        Message = message;
        CreatedAt = createdAt;
    }

    public long Id { get; set; }

    public string UserId { get; private set; }

    public int Rating { get; private set; }

    public string Message { get; private set; }

    public DateTime CreatedAt { get; private set; }
}
