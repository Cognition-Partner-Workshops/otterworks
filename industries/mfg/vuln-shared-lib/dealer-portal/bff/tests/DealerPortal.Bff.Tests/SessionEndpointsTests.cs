using System.Net;
using System.Net.Http.Json;
using DealerPortal.Bff.Session;

namespace DealerPortal.Bff.Tests;

[Collection(BffCollection.Name)]
public sealed class SessionEndpointsTests : IDisposable
{
    private readonly PortalFactory _factory = new();

    public void Dispose() => _factory.Dispose();

    [Fact]
    public async Task SignIn_ForwardsCredentialsAndIssuesHttpOnlySessionCookie()
    {
        var client = _factory.CreateClient(new() { HandleCookies = false });

        var response = await client.PostAsJsonAsync("/bff/session", new { email = StubUpstream.Email, password = "vsl-synthetic-portal-pass" });

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var view = await response.Content.ReadFromJsonAsync<SessionView>();
        Assert.Equal(StubUpstream.DealerId, view!.DealerId);
        Assert.Equal(StubUpstream.Email, view.Email);

        var cookie = Assert.Single(response.Headers.GetValues("Set-Cookie"));
        Assert.StartsWith(PortalSessionService.CookieName + "=", cookie);
        Assert.Contains("httponly", cookie, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("samesite=strict", cookie, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("secure", cookie, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain(StubUpstream.AccessToken, await response.Content.ReadAsStringAsync());

        var upstream = Assert.Single(_factory.Upstream.Requests);
        Assert.Equal("http://dev-api.test/api/identity/signin", upstream.RequestUri!.ToString());
        Assert.Contains("vsl-synthetic-portal-pass", _factory.Upstream.Bodies[0]);
    }

    [Fact]
    public async Task SignIn_ReturnsUnauthorizedWhenUpstreamRejects()
    {
        var client = _factory.CreateClient();
        var response = await client.PostAsJsonAsync("/bff/session", new { email = "someone@dealer.example", password = "nope" });
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        Assert.False(response.Headers.Contains("Set-Cookie"));
    }

    [Fact]
    public async Task SignIn_RejectsMissingFields()
    {
        var client = _factory.CreateClient();
        var response = await client.PostAsJsonAsync("/bff/session", new { email = "", password = "" });
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.Empty(_factory.Upstream.Requests);
    }

    [Fact]
    public async Task GetSession_ReturnsCurrentSession()
    {
        var client = await _factory.SignedInClientAsync();
        var view = await client.GetFromJsonAsync<SessionView>("/bff/session");
        Assert.Equal(StubUpstream.DealerId, view!.DealerId);
    }

    [Fact]
    public async Task GetSession_WithoutCookieIsUnauthorized()
    {
        var response = await _factory.CreateClient().GetAsync("/bff/session");
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task SignOut_ExpiresTheCookie()
    {
        var client = await _factory.SignedInClientAsync();
        var response = await client.DeleteAsync("/bff/session");
        Assert.Equal(HttpStatusCode.NoContent, response.StatusCode);
        var cookie = Assert.Single(response.Headers.GetValues("Set-Cookie"));
        Assert.Contains("expires=Thu, 01 Jan 1970", cookie, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task TamperedCookieIsRejected()
    {
        var client = _factory.CreateClient(new() { HandleCookies = false });
        client.DefaultRequestHeaders.Add("Cookie", $"{PortalSessionService.CookieName}=eyJzdWIiOiJ4In0.bm90LWEtc2lnbmF0dXJl");
        var response = await client.GetAsync("/bff/inventory");
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        Assert.Empty(_factory.Upstream.Requests);
    }
}
