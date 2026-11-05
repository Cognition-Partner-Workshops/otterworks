using Microsoft.EntityFrameworkCore;
using OtterWorks.LegacyPortal.UserPreferences.Models;

namespace OtterWorks.LegacyPortal.UserPreferences.Data;

public class UserPreferencesDbContext : DbContext
{
    public const string Schema = "user_preferences";

    public UserPreferencesDbContext(DbContextOptions<UserPreferencesDbContext> options)
        : base(options)
    {
    }

    public DbSet<UserPreference> Preferences => Set<UserPreference>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        ArgumentNullException.ThrowIfNull(modelBuilder);
        modelBuilder.HasDefaultSchema(Schema);
        modelBuilder.Entity<UserPreference>(entity =>
        {
            entity.ToTable("user_preference", Schema);
            entity.HasKey(p => p.UserId);
            entity.Property(p => p.UserId).HasColumnName("user_id").HasMaxLength(100).ValueGeneratedNever();
            entity.Property(p => p.Theme).HasColumnName("theme").HasMaxLength(20).IsRequired();
            entity.Property(p => p.Locale).HasColumnName("locale").HasMaxLength(20).IsRequired();
            entity.Property(p => p.EmailNotifications).HasColumnName("email_notifications").IsRequired();
        });
    }
}
