using Microsoft.EntityFrameworkCore;
using OtterWorks.LegacyPortal.Feedback.Data;
using OtterWorks.LegacyPortal.Feedback.Services;

namespace OtterWorks.LegacyPortal.Common;

public static partial class PortalModules
{
    static partial void AddFeedback(IServiceCollection services, IConfiguration configuration)
    {
        AddFeedbackDbContext(services);
        services.AddScoped<IFeedbackRepository, FeedbackRepository>();
        services.AddScoped<IFeedbackService, FeedbackService>();
        services.AddScoped<ISchemaInitializer, FeedbackSchemaInitializer>();
    }

    /// <summary>
    /// Same provider selection as <see cref="PersistenceExtensions.AddPortalDbContext{TContext}"/>, but the settings
    /// are read from the built <see cref="IConfiguration"/> so WebApplicationFactory overrides apply.
    /// </summary>
    private static void AddFeedbackDbContext(IServiceCollection services)
    {
        services.AddDbContext<FeedbackDbContext>((provider, options) =>
        {
            var settings = DatabaseSettings.FromConfiguration(provider.GetRequiredService<IConfiguration>());
            if (settings.UsesInMemory)
            {
                options.UseInMemoryDatabase($"{settings.InMemoryName}-{nameof(FeedbackDbContext)}");
            }
            else
            {
                options.UseNpgsql(settings.BuildConnectionString());
            }
        });
    }
}
