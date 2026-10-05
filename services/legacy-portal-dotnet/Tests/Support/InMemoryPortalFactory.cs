using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.Configuration;

namespace OtterWorks.LegacyPortal.Tests.Support;

/// <summary>Hosts the whole app on the EF Core in-memory provider; each factory instance gets its own store.</summary>
public sealed class InMemoryPortalFactory : WebApplicationFactory<Program>
{
    private readonly string _databaseName = $"tests-{Guid.NewGuid():N}";

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.UseEnvironment("Testing");
        builder.ConfigureAppConfiguration((_, config) => config.AddInMemoryCollection(new Dictionary<string, string?>
        {
            ["Database:Provider"] = "InMemory",
            ["Database:InMemoryName"] = _databaseName,
        }));
    }
}
