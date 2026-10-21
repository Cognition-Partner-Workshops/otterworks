using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using OtterWorks.LegacyPortal.Common;
using OtterWorks.LegacyPortal.UserPreferences.Data;

namespace OtterWorks.LegacyPortal.Tests.Unit.UserPreferences;

/// <summary>
/// The shared factories add their <c>Database:*</c> settings through <c>ConfigureAppConfiguration</c>, which minimal
/// hosting applies only when the host is built — after <c>Program</c> has already registered the DbContext from
/// <c>builder.Configuration</c>. This re-registers the context's options from the final test configuration.
/// </summary>
public static class UserPreferencesTestHost
{
    public static WebApplicationFactory<Program> WithUserPreferencesStore(this WebApplicationFactory<Program> factory)
    {
        ArgumentNullException.ThrowIfNull(factory);
        return factory.WithWebHostBuilder(builder => builder.ConfigureServices((context, services) =>
        {
            services.RemoveAll<DbContextOptions<UserPreferencesDbContext>>();
            services.RemoveAll<IDbContextOptionsConfiguration<UserPreferencesDbContext>>();
            services.AddPortalDbContext<UserPreferencesDbContext>(context.Configuration);
        }));
    }
}
