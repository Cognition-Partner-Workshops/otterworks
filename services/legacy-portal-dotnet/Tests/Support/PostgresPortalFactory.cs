using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.Configuration;
using Testcontainers.PostgreSql;

namespace OtterWorks.LegacyPortal.Tests.Support;

/// <summary>
/// Hosts the whole app against a throwaway PostgreSQL 15 container initialised with the Java service's
/// <c>scripts/initdb.sql</c> schemas. Use as an xUnit class fixture (<c>IClassFixture&lt;PostgresPortalFactory&gt;</c>).
/// </summary>
public sealed class PostgresPortalFactory : WebApplicationFactory<Program>, IAsyncLifetime
{
    private const string InitSql =
        "CREATE SCHEMA IF NOT EXISTS announcements; CREATE SCHEMA IF NOT EXISTS user_preferences; CREATE SCHEMA IF NOT EXISTS feedback;";

    private readonly PostgreSqlContainer _container = new PostgreSqlBuilder()
        .WithImage("postgres:15-alpine")
        .WithDatabase("legacyportal")
        .WithUsername("legacyportal")
        .WithPassword("legacyportal")
        .Build();

    public async Task InitializeAsync()
    {
        await _container.StartAsync();
        await _container.ExecScriptAsync(InitSql);
    }

    public new async Task DisposeAsync()
    {
        await base.DisposeAsync();
        await _container.DisposeAsync();
    }

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.UseEnvironment("Testing");
        builder.ConfigureAppConfiguration((_, config) => config.AddInMemoryCollection(new Dictionary<string, string?>
        {
            ["Database:Provider"] = "Postgres",
            ["Database:Host"] = _container.Hostname,
            ["Database:Port"] = _container.GetMappedPublicPort(5432).ToString(System.Globalization.CultureInfo.InvariantCulture),
            ["Database:Name"] = "legacyportal",
            ["Database:User"] = "legacyportal",
            ["Database:Password"] = "legacyportal",
        }));
    }
}
