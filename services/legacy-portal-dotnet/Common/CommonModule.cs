using OtterWorks.LegacyPortal.Configuration;

namespace OtterWorks.LegacyPortal.Common;

public static partial class PortalModules
{
    private static void AddCommon(IServiceCollection services, IConfiguration configuration)
    {
        services.AddSingleton(_ => PortalSettings.Load(
            configuration["Portal:SettingsFile"] ?? Path.Combine(AppContext.BaseDirectory, PortalSettings.FileName)));
        services.AddHealthChecks()
            .AddCheck<PortalDatabaseHealthCheck>("db", tags: [ActuatorController.ReadinessTag]);
    }
}
