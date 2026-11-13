using Microsoft.Extensions.Configuration;
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
        builder.ConfigureAppConfiguration((_, config) => config.AddInMemoryCollection(TestConfiguration.SyntheticSigning.Settings));
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
