using OtterWorks.LegacyPortal.Announcements.Data;
using OtterWorks.LegacyPortal.Announcements.Services;

namespace OtterWorks.LegacyPortal.Common;

public static partial class PortalModules
{
    static partial void AddAnnouncements(IServiceCollection services, IConfiguration configuration)
    {
        services.AddPortalDbContext<AnnouncementsDbContext>(configuration);
        services.AddScoped<IAnnouncementRepository, AnnouncementRepository>();
        services.AddScoped<IAnnouncementService, AnnouncementService>();
        services.AddScoped<ISchemaInitializer, AnnouncementsSchemaInitializer>();
    }
}
