using System.IdentityModel.Tokens.Jwt;
using System.Net;
using System.Net.Http.Json;
using System.Security.Claims;
using System.Text;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.IdentityModel.Tokens;
using Moq;
using OtterWorks.AuditService.Archive;
using OtterWorks.AuditService.Config;
using OtterWorks.AuditService.Controllers;
using OtterWorks.AuditService.Models;
using OtterWorks.AuditService.Services;

namespace AuditService.Tests;

public class AuthorizationTests
{
    private const string Secret = "audit-test-secret-with-more-than-48-bytes-for-signing";

    private static string Token(string user, string role, string type = "access") =>
        new JwtSecurityTokenHandler().WriteToken(new JwtSecurityToken(
            claims: new[] { new Claim("sub", user), new Claim("roles", role), new Claim("type", type) },
            expires: DateTime.UtcNow.AddMinutes(5),
            signingCredentials: new SigningCredentials(new SymmetricSecurityKey(Encoding.UTF8.GetBytes(Secret)),
                SecurityAlgorithms.HmacSha384)));

    private static async Task<WebApplication> Start()
    {
        var builder = WebApplication.CreateBuilder();
        builder.WebHost.UseTestServer();
        builder.Configuration.AddInMemoryCollection(new Dictionary<string, string?> { ["JWT_SECRET"] = Secret });
        builder.Services.AddAuditAuthorization(builder.Configuration);
        var service = new Mock<IAuditService>();
        service.SetReturnsDefault(Task.FromResult(new AuditEventPage()));
        service.SetReturnsDefault(Task.FromResult(new ExportResult()));
        service.SetReturnsDefault(Task.FromResult(new UserActivityReport()));
        service.Setup(s => s.RecordEventAsync(It.IsAny<AuditEventRequest>()))
            .ReturnsAsync(new AuditEventResponse { Id = "event-1" });
        builder.Services.AddSingleton(service.Object);
        builder.Services.AddSingleton(ArchiveStoreOptions.FromEnvironment(_ => null));
        builder.Services.AddSingleton<ArchiveStoreRegistry>();
        var app = builder.Build();
        app.UseAuthentication();
        app.UseAuthorization();
        app.MapAuditEndpoints();
        app.MapArchiveEndpoints();
        await app.StartAsync();
        return app;
    }

    [Theory]
    [InlineData("/api/v1/audit/events")]
    [InlineData("/api/v1/audit/export")]
    public async Task AnonymousIsUnauthorizedAndNormalUserIsForbidden(string path)
    {
        await using var app = await Start();
        using var client = app.GetTestClient();
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.GetAsync(path)).StatusCode);
        client.DefaultRequestHeaders.Authorization = new("Bearer", Token("user-a", "USER"));
        Assert.Equal(HttpStatusCode.Forbidden, (await client.GetAsync(path)).StatusCode);
        client.DefaultRequestHeaders.Authorization = new("Bearer", Token("auditor", "AUDITOR"));
        Assert.Equal(HttpStatusCode.OK, (await client.GetAsync(path)).StatusCode);
    }

    [Fact]
    public async Task UserCannotReadAnotherUsersReportOrArchive()
    {
        await using var app = await Start();
        using var client = app.GetTestClient();
        client.DefaultRequestHeaders.Authorization = new("Bearer", Token("user-a", "USER"));
        Assert.Equal(HttpStatusCode.Forbidden, (await client.GetAsync("/api/v1/audit/reports/user/user-b")).StatusCode);
        Assert.Equal(HttpStatusCode.OK, (await client.GetAsync("/api/v1/audit/reports/user/user-a")).StatusCode);
        Assert.Equal(HttpStatusCode.Forbidden, (await client.GetAsync("/api/v1/audit/archive/doc-a")).StatusCode);
    }

    [Fact]
    public async Task OnlyInternalServiceCanWriteEvents()
    {
        await using var app = await Start();
        using var client = app.GetTestClient();
        var body = new AuditEventRequest { UserId = "user-a", Action = "create", ResourceType = "document", ResourceId = "doc-a" };
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.PostAsJsonAsync("/api/v1/audit/events", body)).StatusCode);
        client.DefaultRequestHeaders.Authorization = new("Bearer", Token("admin", "ADMIN"));
        Assert.Equal(HttpStatusCode.Forbidden, (await client.PostAsJsonAsync("/api/v1/audit/events", body)).StatusCode);
        client.DefaultRequestHeaders.Authorization = new("Bearer", Token("document-service", "SERVICE", "service"));
        Assert.Equal(HttpStatusCode.Created, (await client.PostAsJsonAsync("/api/v1/audit/events", body)).StatusCode);
    }

    [Fact]
    public async Task RefreshAndForgedTokensAreRejected()
    {
        await using var app = await Start();
        using var client = app.GetTestClient();
        client.DefaultRequestHeaders.Authorization = new("Bearer", Token("admin", "ADMIN", "refresh"));
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.GetAsync("/api/v1/audit/events")).StatusCode);
        client.DefaultRequestHeaders.Authorization = new("Bearer", "invalid.signature.token");
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.GetAsync("/api/v1/audit/events")).StatusCode);
    }
}
