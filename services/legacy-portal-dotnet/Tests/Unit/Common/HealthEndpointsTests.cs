using System.Net;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Diagnostics.HealthChecks;
using OtterWorks.LegacyPortal.Common;
using OtterWorks.LegacyPortal.Tests.Support;

namespace OtterWorks.LegacyPortal.Tests.Unit.Common;

public class HealthEndpointsTests : IClassFixture<InMemoryPortalFactory>
{
    private readonly InMemoryPortalFactory _factory;

    public HealthEndpointsTests(InMemoryPortalFactory factory)
    {
        _factory = factory;
    }

    [Theory]
    [InlineData("/health", "{\"status\":\"UP\",\"service\":\"legacy-portal\",\"banner\":\"OtterWorks Portal (on-prem) - contact portal-support@otterworks.example\"}")]
    [InlineData("/actuator/health", "{\"status\":\"UP\",\"groups\":[\"liveness\",\"readiness\"]}")]
    [InlineData("/actuator/health/liveness", "{\"status\":\"UP\"}")]
    [InlineData("/actuator/health/readiness", "{\"status\":\"UP\"}")]
    [InlineData("/actuator/info", "{}")]
    public async Task Endpoints_return_java_bodies(string path, string expectedBody)
    {
        using var client = _factory.CreateClient();

        using var response = await client.GetAsync(new Uri(path, UriKind.Relative));

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        response.Content.Headers.ContentType!.MediaType.Should().Be("application/json");
        (await response.Content.ReadAsStringAsync()).Should().Be(expectedBody);
    }

    [Theory]
    [InlineData("/actuator/health/readiness", "{\"status\":\"DOWN\"}")]
    [InlineData("/actuator/health", "{\"status\":\"DOWN\",\"groups\":[\"liveness\",\"readiness\"]}")]
    public async Task Unhealthy_database_reports_down_with_503(string path, string expectedBody)
    {
        using var factory = WithDatabaseCheck(HealthCheckResult.Unhealthy("down"));
        using var client = factory.CreateClient();

        using var response = await client.GetAsync(new Uri(path, UriKind.Relative));

        response.StatusCode.Should().Be(HttpStatusCode.ServiceUnavailable);
        response.Content.Headers.ContentType!.MediaType.Should().Be("application/json");
        (await response.Content.ReadAsStringAsync()).Should().Be(expectedBody);
    }

    [Fact]
    public async Task Liveness_and_health_stay_up_when_database_is_down()
    {
        using var factory = WithDatabaseCheck(HealthCheckResult.Unhealthy("down"));
        using var client = factory.CreateClient();

        using var liveness = await client.GetAsync(new Uri("/actuator/health/liveness", UriKind.Relative));
        using var health = await client.GetAsync(new Uri("/health", UriKind.Relative));

        liveness.StatusCode.Should().Be(HttpStatusCode.OK);
        (await liveness.Content.ReadAsStringAsync()).Should().Be("{\"status\":\"UP\"}");
        health.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    [Fact]
    public async Task Post_to_health_returns_spring_405()
    {
        using var client = _factory.CreateClient();
        using var content = new StringContent(string.Empty);

        using var response = await client.PostAsync(new Uri("/health", UriKind.Relative), content);

        response.StatusCode.Should().Be(HttpStatusCode.MethodNotAllowed);
        (await response.Content.ReadAsStringAsync()).Should().Contain("\"error\":\"Method Not Allowed\"");
    }

    private Microsoft.AspNetCore.Mvc.Testing.WebApplicationFactory<Program> WithDatabaseCheck(HealthCheckResult result) =>
        _factory.WithWebHostBuilder(builder => builder.ConfigureTestServices(services =>
            services.Configure<HealthCheckServiceOptions>(options =>
            {
                var registrations = options.Registrations.Where(r => r.Name == "db").ToList();
                foreach (var registration in registrations)
                {
                    options.Registrations.Remove(registration);
                }

                options.Registrations.Add(new HealthCheckRegistration(
                    "db", _ => new StaticHealthCheck(result), null, [ActuatorController.ReadinessTag]));
            })));

    private sealed class StaticHealthCheck(HealthCheckResult result) : IHealthCheck
    {
        public Task<HealthCheckResult> CheckHealthAsync(HealthCheckContext context, CancellationToken cancellationToken = default) =>
            Task.FromResult(result);
    }
}
