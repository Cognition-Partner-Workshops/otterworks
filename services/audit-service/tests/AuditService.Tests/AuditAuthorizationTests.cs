using System.IdentityModel.Tokens.Jwt;
using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Security.Claims;
using System.Text;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Microsoft.Extensions.Hosting;
using Microsoft.IdentityModel.Tokens;
using Moq;
using OtterWorks.AuditService.Models;
using OtterWorks.AuditService.Services;

namespace AuditService.Tests;

/// <summary>
/// Regression tests for the audit API authorization gap: previously every route under
/// /api/v1/audit was anonymous, so any caller could read, export or forge the audit log.
/// </summary>
public sealed class AuditAuthorizationTests : IClassFixture<AuditAuthorizationTests.AuditApiFactory>
{
    private const string TestSecret = "audit-authorization-tests-secret-at-least-32-bytes-long";
    private const string AliceId = "22222222-2222-2222-2222-222222222222";

    private readonly AuditApiFactory _factory;

    public AuditAuthorizationTests(AuditApiFactory factory)
    {
        _factory = factory;
    }

    public static IEnumerable<object[]> ReadRoutes => new[]
    {
        new object[] { "/api/v1/audit/events?size=5" },
        new object[] { "/api/v1/audit/events/evt-1" },
        new object[] { $"/api/v1/audit/reports/user/{AliceId}" },
        new object[] { "/api/v1/audit/resources/doc-1/history" },
        new object[] { "/api/v1/audit/reports/compliance" },
        new object[] { "/api/v1/audit/export?format=json" },
    };

    public static IEnumerable<object[]> ArchiveReadRoutes => new[]
    {
        new object[] { "/api/audit/archive/doc-1/events" },
        new object[] { "/api/v1/audit/archive/doc-1" },
        new object[] { "/api/v1/audit/archive/doc-1/events" },
    };

    [Theory]
    [MemberData(nameof(ArchiveReadRoutes))]
    public async Task ArchiveRoutes_WithoutToken_Return401(string path)
    {
        var client = _factory.CreateClient();

        var response = await client.GetAsync(path);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Theory]
    [MemberData(nameof(ArchiveReadRoutes))]
    public async Task ArchiveRoutes_WithUserRole_Return403(string path)
    {
        var client = CreateClient(roles: new[] { "USER" });

        var response = await client.GetAsync(path);

        Assert.Equal(HttpStatusCode.Forbidden, response.StatusCode);
    }

    [Theory]
    [MemberData(nameof(ArchiveReadRoutes))]
    public async Task ArchiveRoutes_WithAdminRole_PassTheAuthorizationGate(string path)
    {
        var client = CreateClient(roles: new[] { "ADMIN" });

        var response = await client.GetAsync(path);

        Assert.DoesNotContain(response.StatusCode, new[] { HttpStatusCode.Unauthorized, HttpStatusCode.Forbidden });
    }

    [Theory]
    [MemberData(nameof(ReadRoutes))]
    public async Task ReadRoutes_WithoutToken_Return401(string path)
    {
        var client = _factory.CreateClient();

        var response = await client.GetAsync(path);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Theory]
    [MemberData(nameof(ReadRoutes))]
    public async Task ReadRoutes_WithUserRole_Return403(string path)
    {
        var client = CreateClient(roles: new[] { "USER" });

        var response = await client.GetAsync(path);

        Assert.Equal(HttpStatusCode.Forbidden, response.StatusCode);
    }

    [Theory]
    [MemberData(nameof(ReadRoutes))]
    public async Task ReadRoutes_WithAdminRole_Return200(string path)
    {
        var client = CreateClient(roles: new[] { "ADMIN" });

        var response = await client.GetAsync(path);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }

    [Theory]
    [InlineData("AUDITOR")]
    [InlineData("SERVICE")]
    public async Task QueryEvents_WithAuditorOrServiceRole_Return200(string role)
    {
        var client = CreateClient(roles: new[] { role });

        var response = await client.GetAsync("/api/v1/audit/events?size=5");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }

    [Fact]
    public async Task ReadRoutes_WithTokenSignedByWrongKey_Return401()
    {
        var client = _factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue(
            "Bearer", CreateToken(new[] { "ADMIN" }, secret: "a-completely-different-secret-that-is-long-enough"));

        var response = await client.GetAsync("/api/v1/audit/export?format=json");

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task ReadRoutes_WithRefreshToken_Return401()
    {
        var client = _factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue(
            "Bearer", CreateToken(new[] { "ADMIN" }, tokenType: "refresh"));

        var response = await client.GetAsync("/api/v1/audit/export?format=json");

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task Archive_WithUserRole_Returns403()
    {
        var client = CreateClient(roles: new[] { "USER" });

        var response = await client.PostAsync("/api/v1/audit/archive", content: null);

        Assert.Equal(HttpStatusCode.Forbidden, response.StatusCode);
    }

    [Theory]
    [InlineData("AUDITOR")]
    [InlineData("SERVICE")]
    public async Task Archive_WithReadOnlyRole_Returns403(string role)
    {
        var client = CreateClient(roles: new[] { role });

        var response = await client.PostAsync("/api/v1/audit/archive", content: null);

        Assert.Equal(HttpStatusCode.Forbidden, response.StatusCode);
    }

    [Fact]
    public async Task Archive_WithAdminRole_Returns200()
    {
        var client = CreateClient(roles: new[] { "ADMIN" });

        var response = await client.PostAsync("/api/v1/audit/archive", content: null);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }

    [Theory]
    [InlineData("USER")]
    [InlineData("ADMIN")]
    public async Task RecordEvent_OverHttp_IsNotExposed(string role)
    {
        var client = CreateClient(roles: new[] { role });

        var response = await client.PostAsJsonAsync("/api/v1/audit/events", new
        {
            userId = AliceId,
            action = "delete",
            resourceType = "document",
            resourceId = "doc-secret-1",
        });

        Assert.NotEqual(HttpStatusCode.Created, response.StatusCode);
        Assert.Contains(response.StatusCode, new[] { HttpStatusCode.NotFound, HttpStatusCode.MethodNotAllowed });
        _factory.AuditService.Verify(
            s => s.RecordEventAsync(It.IsAny<AuditEventRequest>()), Times.Never);
    }

    [Fact]
    public async Task HealthEndpoint_StaysAnonymous()
    {
        var client = _factory.CreateClient();

        var response = await client.GetAsync("/health");

        Assert.NotEqual(HttpStatusCode.Unauthorized, response.StatusCode);
        Assert.NotEqual(HttpStatusCode.Forbidden, response.StatusCode);
    }

    private HttpClient CreateClient(string[] roles)
    {
        var client = _factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", CreateToken(roles));
        return client;
    }

    private static string CreateToken(string[] roles, string secret = TestSecret, string tokenType = "access")
    {
        var key = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(secret));
        var claims = new List<Claim>
        {
            new(JwtRegisteredClaimNames.Sub, "11111111-1111-1111-1111-111111111111"),
            new("type", tokenType),
        };
        claims.AddRange(roles.Select(role => new Claim("roles", role)));

        var token = new JwtSecurityToken(
            claims: claims,
            notBefore: DateTime.UtcNow.AddMinutes(-1),
            expires: DateTime.UtcNow.AddMinutes(5),
            signingCredentials: new SigningCredentials(key, SecurityAlgorithms.HmacSha256));

        return new JwtSecurityTokenHandler().WriteToken(token);
    }

    public sealed class AuditApiFactory : WebApplicationFactory<Program>
    {
        public Mock<IAuditService> AuditService { get; } = new();

        protected override void ConfigureWebHost(IWebHostBuilder builder)
        {
            Environment.SetEnvironmentVariable("JWT_SECRET", TestSecret);
            builder.UseSetting("JWT_SECRET", TestSecret);

            builder.ConfigureServices(services =>
            {
                foreach (var hosted in services.Where(d => d.ServiceType == typeof(IHostedService)).ToList())
                {
                    services.Remove(hosted);
                }

                services.RemoveAll(typeof(IAuditService));
                services.AddSingleton(AuditService.Object);
            });

            AuditService.Setup(s => s.QueryEventsAsync(
                    It.IsAny<string?>(), It.IsAny<string?>(), It.IsAny<string?>(), It.IsAny<string?>(),
                    It.IsAny<DateTime?>(), It.IsAny<DateTime?>(), It.IsAny<int>(), It.IsAny<int>()))
                .ReturnsAsync(new AuditEventPage());
            AuditService.Setup(s => s.GetEventAsync(It.IsAny<string>()))
                .ReturnsAsync(new AuditEventResponse { Id = "evt-1", UserId = AliceId });
            AuditService.Setup(s => s.GetUserActivityReportAsync(It.IsAny<string>(), It.IsAny<string>()))
                .ReturnsAsync(new UserActivityReport { UserId = AliceId });
            AuditService.Setup(s => s.GetResourceHistoryAsync(It.IsAny<string>()))
                .ReturnsAsync(new ResourceHistory());
            AuditService.Setup(s => s.GetComplianceReportAsync(It.IsAny<string>()))
                .ReturnsAsync(new ComplianceReport());
            AuditService.Setup(s => s.ExportAsync(It.IsAny<DateTime>(), It.IsAny<DateTime>(), It.IsAny<string>()))
                .ReturnsAsync(new ExportResult { EventCount = 1 });
            AuditService.Setup(s => s.ArchiveOldEventsAsync())
                .ReturnsAsync(new ArchiveResult());
        }
    }
}
