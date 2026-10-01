using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace OtterWorks.LegacyPortal.Common;

public static class PersistenceExtensions
{
    /// <summary>Registers a bounded context's DbContext against the shared datasource.</summary>
    public static IServiceCollection AddPortalDbContext<TContext>(this IServiceCollection services, IConfiguration configuration)
        where TContext : DbContext
    {
        var settings = DatabaseSettings.FromConfiguration(configuration);
        services.AddDbContext<TContext>(options =>
        {
            if (settings.UsesInMemory)
            {
                options.UseInMemoryDatabase($"{settings.InMemoryName}-{typeof(TContext).Name}");
            }
            else
            {
                options.UseNpgsql(settings.BuildConnectionString());
            }
        });
        return services;
    }

    /// <summary>
    /// Maps a UTC <see cref="DateTime"/> to a PostgreSQL <c>timestamp</c> (without time zone) column, which is
    /// what Hibernate generates for <c>java.time.Instant</c>.
    /// </summary>
    public static PropertyBuilder<DateTime> AsUtcTimestamp(this PropertyBuilder<DateTime> property)
    {
        ArgumentNullException.ThrowIfNull(property);
        return property
            .HasColumnType("timestamp without time zone")
            .HasConversion(
                v => DateTime.SpecifyKind(v, DateTimeKind.Unspecified),
                v => DateTime.SpecifyKind(v, DateTimeKind.Utc));
    }
}
