using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using Identity.Controllers;
using Identity.Models;
using Identity.Repositories;
using Identity.Services;
using Microsoft.Extensions.DependencyInjection;

namespace Identity.Tests;

public sealed class AccountEndpointsTests : IDisposable
{
    private readonly IdentityApiFactory factory = new();
    private readonly HttpClient client;

    public AccountEndpointsTests()
    {
        client = factory.CreateClient();
        factory.Seed();
    }

    private async Task Authenticate()
    {
        var response = await client.PostAsJsonAsync("/api/identity/signin",
            new { email = "dealer-ops@dealer.example", password = "vsl-synthetic-dealer-ops-password" });
        response.EnsureSuccessStatusCode();
        var token = await response.Content.ReadFromJsonAsync<AccessTokenResponse>();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token!.AccessToken);
    }

    [Fact]
    public async Task ProfileReturnsAccountWithoutPassword()
    {
        await Authenticate();
        var response = await client.GetAsync("/api/identity/account");
        response.EnsureSuccessStatusCode();
        var json = await response.Content.ReadFromJsonAsync<JsonElement>();
        Assert.Equal("dealer-ops@dealer.example", json.GetProperty("email").GetString());
        Assert.False(json.TryGetProperty("passwordHash", out _));
    }

    [Fact]
    public async Task ProfileRequiresToken()
    {
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.GetAsync("/api/identity/account")).StatusCode);
    }

    [Fact]
    public async Task PasswordChangeAllowsSubsequentSignIn()
    {
        await Authenticate();
        var response = await client.PostAsJsonAsync("/api/identity/account/password",
            new ChangePasswordRequest("vsl-synthetic-dealer-ops-password", "vsl-synthetic-next-password"));
        Assert.Equal(HttpStatusCode.NoContent, response.StatusCode);
        var signin = await client.PostAsJsonAsync("/api/identity/signin",
            new { email = "dealer-ops@dealer.example", password = "vsl-synthetic-next-password" });
        signin.EnsureSuccessStatusCode();
    }

    [Fact]
    public async Task PasswordChangeChecksCurrentPassword()
    {
        await Authenticate();
        var response = await client.PostAsJsonAsync("/api/identity/account/password",
            new ChangePasswordRequest("vsl-synthetic-other-password", "vsl-synthetic-next-password"));
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task PasswordChangeValidatesLength()
    {
        await Authenticate();
        var response = await client.PostAsJsonAsync("/api/identity/account/password",
            new ChangePasswordRequest("vsl-synthetic-dealer-ops-password", ""));
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    [Fact]
    public async Task ResetConfirmationConsumesStoredToken()
    {
        await client.PostAsJsonAsync("/api/identity/password-reset", new { email = "dealer-ops@dealer.example" });
        int id;
        string token;
        using (var scope = factory.Services.CreateScope())
        {
            var reset = scope.ServiceProvider.GetRequiredService<IdentityContext>().PasswordResets.Single();
            id = reset.Id;
            token = scope.ServiceProvider.GetRequiredService<ResetTokenService>().Read(reset.ProtectedToken);
        }
        var request = new ConfirmResetRequest(id, token, "vsl-synthetic-reset-password");
        var response = await client.PostAsJsonAsync("/api/identity/account/reset-confirm", request);
        Assert.Equal(HttpStatusCode.NoContent, response.StatusCode);
        var repeated = await client.PostAsJsonAsync("/api/identity/account/reset-confirm", request);
        Assert.Equal(HttpStatusCode.BadRequest, repeated.StatusCode);
    }

    [Fact]
    public async Task ResetConfirmationRequiresMatchingToken()
    {
        var response = await client.PostAsJsonAsync("/api/identity/account/reset-confirm",
            new ConfirmResetRequest(99, "vsl-synthetic-other-token", "vsl-synthetic-next-password"));
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    public void Dispose()
    {
        client.Dispose();
        factory.Dispose();
    }

    [Fact]
    public async Task ResetConfirmationRejectsExpiredRequest()
    {
        await client.PostAsJsonAsync("/api/identity/password-reset", new { email = "dealer-ops@dealer.example" });
        int id;
        string token;
        using (var scope = factory.Services.CreateScope())
        {
            var context = scope.ServiceProvider.GetRequiredService<IdentityContext>();
            var reset = context.PasswordResets.Single();
            id = reset.Id;
            token = scope.ServiceProvider.GetRequiredService<ResetTokenService>().Read(reset.ProtectedToken);
            reset.ExpiresAt = DateTimeOffset.FromUnixTimeSeconds(1798761599);
            context.SaveChanges();
        }
        var response = await client.PostAsJsonAsync("/api/identity/account/reset-confirm",
            new ConfirmResetRequest(id, token, "vsl-synthetic-next-password"));
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    [Fact]
    public async Task ResetConfirmationRejectsDifferentToken()
    {
        await client.PostAsJsonAsync("/api/identity/password-reset", new { email = "dealer-ops@dealer.example" });
        using var scope = factory.Services.CreateScope();
        var reset = scope.ServiceProvider.GetRequiredService<IdentityContext>().PasswordResets.Single();
        var response = await client.PostAsJsonAsync("/api/identity/account/reset-confirm",
            new ConfirmResetRequest(reset.Id, "vsl-synthetic-other-token", "vsl-synthetic-next-password"));
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }
}
