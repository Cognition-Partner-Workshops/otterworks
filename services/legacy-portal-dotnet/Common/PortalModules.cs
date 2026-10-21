namespace OtterWorks.LegacyPortal.Common;

/// <summary>
/// Registration seam for the bounded contexts. Each context implements its partial method in its own folder
/// (e.g. <c>Announcements/AnnouncementsModule.cs</c>), registering its DbContext, repository, service,
/// validators and <see cref="ISchemaInitializer"/>. Contexts never reference each other.
/// </summary>
public static partial class PortalModules
{
    public static IServiceCollection AddPortalModules(this IServiceCollection services, IConfiguration configuration)
    {
        AddCommon(services, configuration);
        AddAnnouncements(services, configuration);
        AddUserPreferences(services, configuration);
        AddFeedback(services, configuration);
        return services;
    }

    static partial void AddAnnouncements(IServiceCollection services, IConfiguration configuration);

    static partial void AddUserPreferences(IServiceCollection services, IConfiguration configuration);

    static partial void AddFeedback(IServiceCollection services, IConfiguration configuration);
}
