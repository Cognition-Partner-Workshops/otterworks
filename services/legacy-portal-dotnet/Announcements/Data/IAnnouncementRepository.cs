using OtterWorks.LegacyPortal.Announcements.Models;

namespace OtterWorks.LegacyPortal.Announcements.Data;

/// <summary>Port of the Spring Data <c>AnnouncementRepository</c> (JpaRepository&lt;Announcement, Long&gt;).</summary>
public interface IAnnouncementRepository
{
    /// <summary>Inserts a new announcement (id 0) or persists changes to an existing one.</summary>
    Task<Announcement> SaveAsync(Announcement announcement, CancellationToken cancellationToken);

    Task<Announcement?> FindByIdAsync(long id, CancellationToken cancellationToken);

    /// <summary>All rows with no ORDER BY (JpaRepository.findAll): the database's physical order.</summary>
    Task<IReadOnlyList<Announcement>> FindAllAsync(CancellationToken cancellationToken);

    Task<IReadOnlyList<Announcement>> FindByPublishedTrueOrderByCreatedAtDescAsync(CancellationToken cancellationToken);
}
