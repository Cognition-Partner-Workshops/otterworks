using OtterWorks.LegacyPortal.Feedback.Data;
using OtterWorks.LegacyPortal.Feedback.Services;

namespace OtterWorks.LegacyPortal.Common;

public static partial class PortalModules
{
    static partial void AddFeedback(IServiceCollection services, IConfiguration configuration)
    {
        services.AddPortalDbContext<FeedbackDbContext>(configuration);
        services.AddScoped<IFeedbackRepository, FeedbackRepository>();
        services.AddScoped<IFeedbackService, FeedbackService>();
        services.AddScoped<ISchemaInitializer, FeedbackSchemaInitializer>();
    }
}
