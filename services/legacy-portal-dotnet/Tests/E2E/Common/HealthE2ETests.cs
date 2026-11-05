using System.Globalization;
using System.Net;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.Configuration;
using Testcontainers.PostgreSql;

namespace OtterWorks.LegacyPortal.Tests.E2E.Common;

/// <summary>Health and actuator endpoints against a real PostgreSQL 15, including the database going away.</summary>
public sealed class HealthE2ETests : IAsyncLifetime
{
    private readonly PostgreSqlContainer _container = new PostgreSqlBuilder()
        .WithImage("postgres:15-alpine")
        .WithDatabase("legacyportal")
        .WithUsername("legacyportal")
        .WithPassword("legacyportal")
        .Build();

    private WebApplicationFactory<Program>? _factory;

    public async Task InitializeAsync()
    {
        await _container.StartAsync();
        await _container.ExecScriptAsync(
            "CREATE SCHEMA IF NOT EXISTS announcements; CREATE SCHEMA IF NOT EXISTS user_preferences; CREATE SCHEMA IF NOT EXISTS feedback;");
        var port = _container.GetMappedPublicPort(5432).ToString(CultureInfo.InvariantCulture);
        _factory = new WebApplicationFactory<Program>().WithWebHostBuilder(builder =>
        {
            builder.UseEnvironment("Testing");
            builder.ConfigureAppConfiguration((_, config) => config.AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["Database:Provider"] = "Postgres",
                ["Database:Host"] = _container.Hostname,
                ["Database:Port"] = port,
                ["Database:Name"] = "legacyportal",
                ["Database:User"] = "legacyportal",
                ["Database:Password"] = "legacyportal",
            }));
        });
    }

    public async Task DisposeAsync()
    {
        if (_factory is not null)
        {
            await _factory.DisposeAsync();
        }

        await _container.DisposeAsync();
    }

    [Fact]
    public async Task Readiness_tracks_the_database()
    {
        using var client = _factory!.CreateClient();

        using var health = await client.GetAsync(new Uri("/health", UriKind.Relative));
        health.StatusCode.Should().Be(HttpStatusCode.OK);
        (await health.Content.ReadAsStringAsync()).Should().Be(
            "{\"status\":\"UP\",\"service\":\"legacy-portal\",\"banner\":\"OtterWorks Portal (on-prem) - contact portal-support@otterworks.example\"}");

        await AssertAsync(client, "/actuator/health/readiness", HttpStatusCode.OK, "{\"status\":\"UP\"}");
        await AssertAsync(client, "/actuator/health", HttpStatusCode.OK, "{\"status\":\"UP\",\"groups\":[\"liveness\",\"readiness\"]}");

        await _container.StopAsync();

        await AssertAsync(client, "/actuator/health/readiness", HttpStatusCode.ServiceUnavailable, "{\"status\":\"DOWN\"}");
        await AssertAsync(client, "/actuator/health", HttpStatusCode.ServiceUnavailable, "{\"status\":\"DOWN\",\"groups\":[\"liveness\",\"readiness\"]}");
        await AssertAsync(client, "/actuator/health/liveness", HttpStatusCode.OK, "{\"status\":\"UP\"}");
        await AssertAsync(client, "/actuator/info", HttpStatusCode.OK, "{}");
    }

    private static async Task AssertAsync(HttpClient client, string path, HttpStatusCode status, string body)
    {
        using var response = await client.GetAsync(new Uri(path, UriKind.Relative));
        response.StatusCode.Should().Be(status, path);
        response.Content.Headers.ContentType!.MediaType.Should().Be("application/json");
        (await response.Content.ReadAsStringAsync()).Should().Be(body, path);
    }
}
