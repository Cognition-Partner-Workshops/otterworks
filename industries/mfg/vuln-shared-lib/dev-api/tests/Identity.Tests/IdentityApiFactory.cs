using Identity.Repositories;
using Identity.Models;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Platform.Shared.Crypto;

namespace Identity.Tests;

public sealed class IdentityApiFactory : WebApplicationFactory<Identity.Program>
{
    private readonly SqliteConnection connection = new("Data Source=:memory:");

    public IdentityApiFactory() => connection.Open();

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.ConfigureServices(services =>
        {
            services.RemoveAll<DbContextOptions<IdentityContext>>();
            services.AddDbContext<IdentityContext>(options => options.UseSqlite(connection));
            services.RemoveAll<TimeProvider>();
            services.AddSingleton<TimeProvider>(new AccountClock());
        });
    }

    public void Seed()
    {
        using var scope = Services.CreateScope();
        var database = scope.ServiceProvider.GetRequiredService<IdentityContext>();
        if (database.Accounts.Any())
            return;
        database.Accounts.Add(new Account
        {
            Email = "dealer-ops@dealer.example",
            DealerId = "D-1001",
            PasswordHash = PasswordHasher.Hash("vsl-synthetic-dealer-ops-password"),
            Roles = "dealer"
        });
        database.SaveChanges();
    }

    public string? ClientSecret { get; init; } = "vsl-synthetic-test-introspection-secret";

    protected override Microsoft.Extensions.Hosting.IHost CreateHost(Microsoft.Extensions.Hosting.IHostBuilder builder)
    {
        builder.ConfigureAppConfiguration((_, config) =>
            Microsoft.Extensions.Configuration.MemoryConfigurationBuilderExtensions.AddInMemoryCollection(config,
                new Dictionary<string, string?> { ["Identity:ClientSecret"] = ClientSecret }));
        return base.CreateHost(builder);
    }

    protected override void Dispose(bool disposing)
    {
        base.Dispose(disposing);
        if (disposing)
            connection.Dispose();
    }
}

public sealed class AccountClock : TimeProvider
{
    public override DateTimeOffset GetUtcNow() => DateTimeOffset.FromUnixTimeSeconds(1798761600);
}
