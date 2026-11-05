using OtterWorks.LegacyPortal.UserPreferences.Data;
using OtterWorks.LegacyPortal.UserPreferences.Services;

namespace OtterWorks.LegacyPortal.Common;

public static partial class PortalModules
{
    static partial void AddUserPreferences(IServiceCollection services, IConfiguration configuration)
    {
        services.AddPortalDbContext<UserPreferencesDbContext>(configuration);
        services.AddScoped<IUserPreferenceRepository, UserPreferenceRepository>();
        services.AddScoped<IUserPreferenceService, UserPreferenceService>();
        services.AddScoped<ISchemaInitializer, UserPreferencesSchemaInitializer>();
    }
}
