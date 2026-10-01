using Microsoft.EntityFrameworkCore;
using OtterWorks.LegacyPortal.Feedback.Models;

namespace OtterWorks.LegacyPortal.Feedback.Data;

/// <summary>Port of the Java <c>FeedbackRepository</c> (Spring Data JPA).</summary>
public interface IFeedbackRepository
{
    Task<FeedbackEntry> SaveAsync(FeedbackEntry entry, CancellationToken cancellationToken = default);

    Task<IReadOnlyList<FeedbackEntry>> FindByUserIdOrderByCreatedAtDescAsync(string userId, CancellationToken cancellationToken = default);

    Task<IReadOnlyList<FeedbackEntry>> FindAllAsync(CancellationToken cancellationToken = default);
}

public sealed class FeedbackRepository : IFeedbackRepository
{
    private readonly FeedbackDbContext _db;

    public FeedbackRepository(FeedbackDbContext db)
    {
        _db = db;
    }

    public async Task<FeedbackEntry> SaveAsync(FeedbackEntry entry, CancellationToken cancellationToken = default)
    {
        _db.Entries.Add(entry);
        await _db.SaveChangesAsync(cancellationToken);
        return entry;
    }

    public async Task<IReadOnlyList<FeedbackEntry>> FindByUserIdOrderByCreatedAtDescAsync(string userId, CancellationToken cancellationToken = default)
    {
        return await _db.Entries
            .AsNoTracking()
            .Where(e => e.UserId == userId)
            .OrderByDescending(e => e.CreatedAt)
            .ToListAsync(cancellationToken);
    }

    public async Task<IReadOnlyList<FeedbackEntry>> FindAllAsync(CancellationToken cancellationToken = default)
    {
        return await _db.Entries.AsNoTracking().ToListAsync(cancellationToken);
    }
}
