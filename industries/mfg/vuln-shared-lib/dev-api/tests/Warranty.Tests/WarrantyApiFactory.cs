using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Warranty.Models;
using Warranty.Repositories;

namespace Warranty.Tests;

public sealed class WarrantyApiFactory : WebApplicationFactory<Warranty.Program>
{
    private readonly SqliteConnection connection = new("Data Source=:memory:");
    public string AttachmentRoot { get; } = Path.Combine(AppContext.BaseDirectory, "data", Guid.NewGuid().ToString("N"));

    public WarrantyApiFactory()
    {
        connection.Open();
        Directory.CreateDirectory(Path.Combine(AttachmentRoot, "1"));
        File.WriteAllText(Path.Combine(AttachmentRoot, "1", "receipt.txt"), "Parts receipt");
    }

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.ConfigureAppConfiguration((_, config) => config.AddInMemoryCollection(TestConfiguration.SyntheticSigning.Settings));
        builder.ConfigureAppConfiguration((_, config) => config.AddInMemoryCollection(
            new Dictionary<string, string?> { ["Warranty:AttachmentRoot"] = AttachmentRoot }));
        builder.ConfigureServices(services =>
        {
            services.RemoveAll<DbContextOptions<WarrantyContext>>();
            services.AddDbContext<WarrantyContext>(options => options.UseSqlite(connection));
        });
    }

    public void Seed()
    {
        using var scope = Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<WarrantyContext>();
        context.Claims.AddRange(
            new Claim { Id = 1, DealerId = "D-1001", Vin = "VIN1001", Description = "Door latch", SubmittedAt = DateTimeOffset.UtcNow },
            new Claim { Id = 2, DealerId = "D-2001", Vin = "VIN2001", Description = "Seat adjustment", SubmittedAt = DateTimeOffset.UtcNow });
        context.SaveChanges();
    }

    protected override void Dispose(bool disposing)
    {
        base.Dispose(disposing);
        if (disposing)
        {
            connection.Dispose();
            if (Directory.Exists(AttachmentRoot))
            {
                Directory.Delete(AttachmentRoot, true);
            }
        }
    }
}
