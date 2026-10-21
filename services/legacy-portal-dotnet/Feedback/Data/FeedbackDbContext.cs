using Microsoft.EntityFrameworkCore;
using OtterWorks.LegacyPortal.Common;
using OtterWorks.LegacyPortal.Feedback.Models;

namespace OtterWorks.LegacyPortal.Feedback.Data;

public class FeedbackDbContext : DbContext
{
    public const string Schema = "feedback";

    public FeedbackDbContext(DbContextOptions<FeedbackDbContext> options)
        : base(options)
    {
    }

    public DbSet<FeedbackEntry> Entries => Set<FeedbackEntry>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        ArgumentNullException.ThrowIfNull(modelBuilder);
        modelBuilder.HasDefaultSchema(Schema);
        modelBuilder.Entity<FeedbackEntry>(entity =>
        {
            entity.ToTable("feedback", Schema);
            entity.HasKey(e => e.Id);
            entity.Property(e => e.Id).HasColumnName("id").ValueGeneratedOnAdd();
            entity.Property(e => e.UserId).HasColumnName("user_id").HasMaxLength(100).IsRequired();
            entity.Property(e => e.Rating).HasColumnName("rating").IsRequired();
            entity.Property(e => e.Message).HasColumnName("message").HasMaxLength(2000).IsRequired();
            entity.Property(e => e.CreatedAt).HasColumnName("created_at").IsRequired().AsUtcTimestamp();
        });
    }
}
