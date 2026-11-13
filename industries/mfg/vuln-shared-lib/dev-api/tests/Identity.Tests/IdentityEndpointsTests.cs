using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using Identity.Models;
using Identity.Repositories;
using Microsoft.Extensions.DependencyInjection;
using Platform.Shared.Crypto;

namespace Identity.Tests;

public sealed class IdentityEndpointsTests : IDisposable
{
    private readonly IdentityApiFactory factory = new();
    private readonly HttpClient client;

    public IdentityEndpointsTests()
    {
        client = factory.CreateClient(new() { AllowAutoRedirect = false });
        factory.Seed();
    }

    private async Task<AccessTokenResponse> SignIn()
    {
        var response = await client.PostAsJsonAsync("/api/identity/signin",
            new { email = "dealer-ops@dealer.example", password = "vsl-synthetic-dealer-ops-password" });
        response.EnsureSuccessStatusCode();
        return (await response.Content.ReadFromJsonAsync<AccessTokenResponse>())!;
    }

    [Fact]
    public async Task SignInReturnsOrderedToken()
    {
        var response = await SignIn();
        Assert.Equal("v1.eyJzdWIiOiJkZWFsZXItb3BzQGRlYWxlci5leGFtcGxlIiwiZGVhbGVyIjoiRC0xMDAxIiwicm9sZXMiOlsiZGVhbGVyIl0sImlhdCI6MTc5ODc2MTYwMCwiZXhwIjoxNzk4NzY1MjAwfQ.tsR_nbfw6TFkFEydowMEG_yXhQQgMO3oYDFVNkxeA1s", response.AccessToken);
        Assert.Equal("Bearer", response.TokenType);
        Assert.Equal(3600, response.ExpiresIn);
        Assert.Equal("D-1001", response.DealerId);
    }

    [Theory]
    [InlineData("dealer-ops@dealer.example", "vsl-synthetic-other-password")]
    [InlineData("absent@dealer.example", "vsl-synthetic-dealer-ops-password")]
    public async Task SignInRequiresMatchingAccount(string email, string password)
    {
        var response = await client.PostAsJsonAsync("/api/identity/signin", new { email, password });
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task SignInValidatesBody()
    {
        var response = await client.PostAsJsonAsync("/api/identity/signin", new { email = "", password = "" });
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    [Fact]
    public async Task IntrospectionReadsTokenForPortal()
    {
        var token = await SignIn();
        client.DefaultRequestHeaders.Add("X-Client-Secret", factory.ClientSecret);
        var response = await client.PostAsJsonAsync("/api/identity/introspect", new { token.AccessToken });
        var body = await response.Content.ReadFromJsonAsync<JsonElement>();
        Assert.True(body.GetProperty("active").GetBoolean());
        Assert.Equal("D-1001", body.GetProperty("dealer").GetString());
        var invalid = await client.PostAsJsonAsync("/api/identity/introspect", new { accessToken = "other" });
        Assert.False((await invalid.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("active").GetBoolean());
    }

    [Fact]
    public async Task IntrospectionRequiresClient()
    {
        var response = await client.PostAsJsonAsync("/api/identity/introspect", new { accessToken = "other" });
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task DeviceRegistrationStoresFingerprint()
    {
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", (await SignIn()).AccessToken);
        var response = await client.PostAsJsonAsync("/api/identity/devices", new { deviceId = "tablet-1", userAgent = "DealerTablet/1" });
        Assert.Equal(HttpStatusCode.Created, response.StatusCode);
        var device = await response.Content.ReadFromJsonAsync<RegisteredDevice>();
        Assert.Equal(64, device!.Fingerprint.Length);
        Assert.Equal(DeviceFingerprint.Compute("DealerTablet/1", "tablet-1"), device.Fingerprint);
        Assert.NotEqual(Convert.ToHexString(System.Security.Cryptography.MD5.HashData(
            System.Text.Encoding.UTF8.GetBytes("DealerTablet/1tablet-1"))), device.Fingerprint);
        using var scope = factory.Services.CreateScope();
        Assert.Equal(device.Fingerprint, scope.ServiceProvider.GetRequiredService<IdentityContext>().Devices.Single().Fingerprint);
    }

    [Fact]
    public async Task FingerprintRegression_IsStableAndSeparatesFields()
    {
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", (await SignIn()).AccessToken);
        async Task<string> Register(string agent, string id)
        {
            var response = await client.PostAsJsonAsync("/api/identity/devices", new { userAgent = agent, deviceId = id });
            Assert.Equal(HttpStatusCode.Created, response.StatusCode);
            return (await response.Content.ReadFromJsonAsync<RegisteredDevice>())!.Fingerprint;
        }
        var first = await Register("ab", "c");
        Assert.Equal(first, await Register("ab", "c"));
        Assert.NotEqual(first, await Register("a", "bc"));
        Assert.Equal(64, first.Length);
        Assert.Equal(DeviceFingerprint.Compute("ab", "c"), first);
    }

    [Fact]
    public async Task DeviceRegistrationRequiresToken()
    {
        var response = await client.PostAsJsonAsync("/api/identity/devices", new { deviceId = "tablet-1", userAgent = "DealerTablet/1" });
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task DeviceFingerprintSeparatesFields()
    {
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", (await SignIn()).AccessToken);
        var response = await client.PostAsJsonAsync("/api/identity/devices", new { userAgent = "ab", deviceId = "c" });
        response.EnsureSuccessStatusCode();
        var device = await response.Content.ReadFromJsonAsync<RegisteredDevice>();
        Assert.Equal(DeviceFingerprint.Compute("ab", "c"), device!.Fingerprint);
        Assert.NotEqual(DeviceFingerprint.Compute("a", "bc"), device.Fingerprint);
        var repeated = await client.PostAsJsonAsync("/api/identity/devices", new { userAgent = "ab", deviceId = "c" });
        repeated.EnsureSuccessStatusCode();
        Assert.Equal(device.Fingerprint, (await repeated.Content.ReadFromJsonAsync<RegisteredDevice>())!.Fingerprint);
    }

    [Fact]
    public async Task RememberMeWritesCookieAndSignOutClearsIt()
    {
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", (await SignIn()).AccessToken);
        var response = await client.PostAsJsonAsync("/api/identity/remember-me", new { email = "dealer-ops@dealer.example" });
        Assert.Equal(HttpStatusCode.NoContent, response.StatusCode);
        Assert.Contains("remember_me=", response.Headers.GetValues("Set-Cookie").Single());
        var signout = await client.GetAsync("/api/identity/signout?returnUrl=https%3A%2F%2Fportal.dealer.example%2F");
        Assert.Equal(HttpStatusCode.Redirect, signout.StatusCode);
        Assert.Equal("https://portal.dealer.example/", signout.Headers.Location!.ToString());
        Assert.Contains("remember_me=", signout.Headers.GetValues("Set-Cookie").Single());
    }

    [Fact]
    public async Task RememberMeRequiresAccountToken()
    {
        var response = await client.PostAsJsonAsync("/api/identity/remember-me", new { email = "dealer-ops@dealer.example" });
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Theory]
    [InlineData("dealer-ops@dealer.example", 1)]
    [InlineData("absent@dealer.example", 0)]
    public async Task PasswordResetStoresOnlyRegisteredAccount(string email, int count)
    {
        var response = await client.PostAsJsonAsync("/api/identity/password-reset", new { email });
        Assert.Equal(HttpStatusCode.Accepted, response.StatusCode);
        using var scope = factory.Services.CreateScope();
        Assert.Equal(count, scope.ServiceProvider.GetRequiredService<IdentityContext>().PasswordResets.Count());
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData(" ")]
    public async Task IntrospectionFailsClosedWithoutConfiguredSecret(string? secret)
    {
        using var unconfigured = new IdentityApiFactory { ClientSecret = secret };
        using var anonymous = unconfigured.CreateClient();
        var response = await anonymous.PostAsJsonAsync("/api/identity/introspect", new { accessToken = "other" });
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task IntrospectionRejectsCommittedSecret()
    {
        client.DefaultRequestHeaders.Add("X-Client-Secret", "vsl-synthetic-identity-client-secret-portal");
        var response = await client.PostAsJsonAsync("/api/identity/introspect", new { accessToken = "other" });
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public void ShippedSettingsHaveNoClientSecret()
    {
        using var settings = JsonDocument.Parse(File.ReadAllText(Path.Combine(factory.Server.Services
            .GetRequiredService<Microsoft.AspNetCore.Hosting.IWebHostEnvironment>().ContentRootPath, "appsettings.json")));
        Assert.False(settings.RootElement.GetProperty("Identity").TryGetProperty("ClientSecret", out _));
    }

    [Theory]
    [InlineData("https://evil.example/", "/")]
    [InlineData("//evil.example", "/")]
    [InlineData("/\\evil.example", "/")]
    [InlineData("http://portal.dealer.example/", "/")]
    [InlineData("https://portal.dealer.example.evil.example/", "/")]
    [InlineData("javascript:alert(1)", "/")]
    [InlineData("/dashboard", "/dashboard")]
    [InlineData("", "/")]
    public async Task SignOutValidatesReturnUrl(string returnUrl, string expected)
    {
        var response = await client.GetAsync("/api/identity/signout?returnUrl=" + Uri.EscapeDataString(returnUrl));
        Assert.Equal(HttpStatusCode.Redirect, response.StatusCode);
        Assert.Equal(expected, response.Headers.Location!.ToString());
        Assert.Contains("remember_me=;", response.Headers.GetValues("Set-Cookie").Single());
        Assert.Contains("expires=", response.Headers.GetValues("Set-Cookie").Single());
    }

    public void Dispose()
    {
        client.Dispose();
        factory.Dispose();
    }
}
