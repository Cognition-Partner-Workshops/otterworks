using Microsoft.EntityFrameworkCore;
using OtterWorks.LegacyPortal.Announcements.Models;

namespace OtterWorks.LegacyPortal.Announcements.Data;

public sealed class AnnouncementRepository : IAnnouncementRepository
{
    private readonly AnnouncementsDbContext _db;

    public AnnouncementRepository(AnnouncementsDbContext db)
    {
        _db = db;
    }

    public async Task<Announcement> SaveAsync(Announcement announcement, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(announcement);
        if (announcement.Id == 0)
        {
            _db.Announcements.Add(announcement);
        }
        else if (_db.Entry(announcement).State == EntityState.Detached)
        {
            _db.Announcements.Update(announcement);
        }

        await _db.SaveChangesAsync(cancellationToken);
        return announcement;
    }

    public async Task<Announcement?> FindByIdAsync(long id, CancellationToken cancellationToken)
    {
        return await _db.Announcements.FindAsync([id], cancellationToken);
    }

    public async Task<IReadOnlyList<Announcement>> FindAllAsync(CancellationToken cancellationToken)
    {
        return await _db.Announcements.AsNoTracking().ToListAsync(cancellationToken);
    }

    public async Task<IReadOnlyList<Announcement>> FindByPublishedTrueOrderByCreatedAtDescAsync(CancellationToken cancellationToken)
    {
        return await _db.Announcements.AsNoTracking()
            .Where(a => a.Published)
            .OrderByDescending(a => a.CreatedAt)
            .ToListAsync(cancellationToken);
    }
}
