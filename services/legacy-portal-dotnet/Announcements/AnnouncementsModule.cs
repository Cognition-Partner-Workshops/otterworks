using Microsoft.EntityFrameworkCore;
using OtterWorks.LegacyPortal.Announcements.Data;
using OtterWorks.LegacyPortal.Announcements.Services;

namespace OtterWorks.LegacyPortal.Common;

public static partial class PortalModules
{
    static partial void AddAnnouncements(IServiceCollection services, IConfiguration configuration)
    {
        // Same provider selection as AddPortalDbContext, but DatabaseSettings are read when the DbContext is first
        // configured: WebApplicationFactory adds its configuration only when the host is built, after modules run.
        services.AddDbContext<AnnouncementsDbContext>(options =>
        {
            var settings = DatabaseSettings.FromConfiguration(configuration);
            if (settings.UsesInMemory)
            {
                options.UseInMemoryDatabase($"{settings.InMemoryName}-{nameof(AnnouncementsDbContext)}");
            }
            else
            {
                options.UseNpgsql(settings.BuildConnectionString());
            }
        });
        services.AddScoped<IAnnouncementRepository, AnnouncementRepository>();
        services.AddScoped<IAnnouncementService, AnnouncementService>();
        services.AddScoped<ISchemaInitializer, AnnouncementsSchemaInitializer>();
    }
}
