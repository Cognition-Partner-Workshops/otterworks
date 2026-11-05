using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata;
using OtterWorks.LegacyPortal.Announcements.Models;
using OtterWorks.LegacyPortal.Common;

namespace OtterWorks.LegacyPortal.Announcements.Data;

public class AnnouncementsDbContext : DbContext
{
    public const string Schema = "announcements";

    public AnnouncementsDbContext(DbContextOptions<AnnouncementsDbContext> options)
        : base(options)
    {
    }

    public DbSet<Announcement> Announcements => Set<Announcement>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        ArgumentNullException.ThrowIfNull(modelBuilder);
        modelBuilder.HasDefaultSchema(Schema);
        modelBuilder.Entity<Announcement>(entity =>
        {
            entity.ToTable("announcement");
            entity.HasKey(a => a.Id);
            entity.Property(a => a.Id).HasColumnName("id").ValueGeneratedOnAdd();
            entity.Property(a => a.Title).HasColumnName("title").HasMaxLength(200).IsRequired();
            entity.Property(a => a.Body).HasColumnName("body").HasMaxLength(4000).IsRequired();
            entity.Property(a => a.Published).HasColumnName("published").IsRequired();
            entity.Property(a => a.CreatedAt).HasColumnName("created_at").AsUtcTimestamp().IsRequired()
                .Metadata.SetAfterSaveBehavior(PropertySaveBehavior.Ignore);
        });
    }
}
