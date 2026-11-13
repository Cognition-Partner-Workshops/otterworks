using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using DealerPortal.Bff.Notices;
using DealerPortal.Bff.Upstream;

namespace DealerPortal.Bff.Tests;

[Collection(BffCollection.Name)]
public sealed class DealerEndpointsTests : IDisposable
{
    private readonly PortalFactory _factory = new();

    public void Dispose() => _factory.Dispose();

    [Fact]
    public async Task Inventory_ProxiesUpstreamWithBearerTokenAndDealerId()
    {
        var client = await _factory.SignedInClientAsync();

        var vehicles = await client.GetFromJsonAsync<List<Vehicle>>("/bff/inventory");

        Assert.Equal(2, vehicles!.Count);
        Assert.Equal("Ranger LT", vehicles[0].Model);
        var upstream = _factory.Upstream.Requests[^1];
        Assert.Equal("/api/dealer/inventory?dealerId=D-1001", upstream.RequestUri!.PathAndQuery);
        Assert.Equal($"Bearer {StubUpstream.AccessToken}", upstream.Headers.Authorization!.ToString());
    }

    [Fact]
    public async Task InventoryDetail_FindsVehicleByVin()
    {
        var client = await _factory.SignedInClientAsync();
        var vehicle = await client.GetFromJsonAsync<Vehicle>("/bff/inventory/1vsla0000aa000002");
        Assert.Equal("Harbor XL", vehicle!.Model);
    }

    [Fact]
    public async Task InventoryDetail_UnknownVinIsNotFound()
    {
        var client = await _factory.SignedInClientAsync();
        var response = await client.GetAsync("/bff/inventory/1VSLA0000AA999999");
        Assert.Equal(HttpStatusCode.NotFound, response.StatusCode);
    }

    [Fact]
    public async Task DealerEndpoints_RequireASession()
    {
        var client = _factory.CreateClient();
        foreach (var path in new[] { "/bff/inventory", "/bff/claims", "/bff/notices" })
        {
            Assert.Equal(HttpStatusCode.Unauthorized, (await client.GetAsync(path)).StatusCode);
        }
    }

    [Fact]
    public async Task Claims_ListsDealerClaims()
    {
        var client = await _factory.SignedInClientAsync();
        var claims = await client.GetFromJsonAsync<List<WarrantyClaim>>("/bff/claims");
        var claim = Assert.Single(claims!);
        Assert.Equal("WC-1", claim.Id);
        Assert.Equal("/api/warranty/claims?dealerId=D-1001", _factory.Upstream.Requests[^1].RequestUri!.PathAndQuery);
    }

    [Fact]
    public async Task SubmitClaim_ForwardsBodyAndReturnsCreated()
    {
        var client = await _factory.SignedInClientAsync();

        var response = await client.PostAsJsonAsync("/bff/claims", new { vin = "1VSLA0000AA000001", description = "Door seal leaks" });

        Assert.Equal(HttpStatusCode.Created, response.StatusCode);
        Assert.Equal("/bff/claims/WC-2", response.Headers.Location!.ToString());
        var claim = await response.Content.ReadFromJsonAsync<WarrantyClaim>();
        Assert.Equal("Door seal leaks", claim!.Description);
        using var sent = JsonDocument.Parse(_factory.Upstream.Bodies[^1]);
        Assert.Equal("1VSLA0000AA000001", sent.RootElement.GetProperty("vin").GetString());
    }

    [Fact]
    public async Task SubmitClaim_RejectsEmptyDescription()
    {
        var client = await _factory.SignedInClientAsync();
        var response = await client.PostAsJsonAsync("/bff/claims", new { vin = "1VSLA0000AA000001", description = " " });
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    [Fact]
    public async Task UpstreamUnauthorized_ClearsTheSession()
    {
        var client = await _factory.SignedInClientAsync();
        _factory.Upstream.ForceStatus = HttpStatusCode.Unauthorized;

        var response = await client.GetAsync("/bff/claims");

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        Assert.Contains(response.Headers.GetValues("Set-Cookie"), c => c.StartsWith("dp_session=;", StringComparison.Ordinal));
    }

    [Fact]
    public async Task UpstreamFailure_IsBadGateway()
    {
        var client = await _factory.SignedInClientAsync();
        _factory.Upstream.ForceStatus = HttpStatusCode.InternalServerError;
        Assert.Equal(HttpStatusCode.BadGateway, (await client.GetAsync("/bff/inventory")).StatusCode);
    }

    [Fact]
    public async Task Notices_ReturnsTheConfiguredFeed()
    {
        var client = await _factory.SignedInClientAsync();

        var notices = await client.GetFromJsonAsync<List<DealerNotice>>("/bff/notices");

        var notice = Assert.Single(notices!);
        Assert.Equal("Brake hose inspection", notice.Title);
        Assert.Equal("https://bulletins.oem.example/dealer-notices.json", _factory.Upstream.Requests[^1].RequestUri!.ToString());
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public async Task Notices_BlockedHostOrRedirectNeverSends(bool redirect)
    {
        using var factory = new PortalFactory(redirect ? null : new Dictionary<string, string?>
        {
            ["Portal:NoticeFeedUrl"] = "https://blocked.example/dealer-notices.json"
        });
        if (redirect) factory.Upstream.NoticeRedirect = new Uri("https://blocked.example/dealer-notices.json");
        using var client = await factory.SignedInClientAsync();
        Assert.Equal(HttpStatusCode.BadGateway, (await client.GetAsync("/bff/notices")).StatusCode);
        Assert.DoesNotContain(factory.Upstream.Requests, request => request.RequestUri!.Host == "blocked.example");
        Assert.Equal(redirect ? 1 : 0, factory.Upstream.Requests.Count(request => request.RequestUri!.Host == "bulletins.oem.example"));
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("https://malformed.example/")]
    public async Task Notices_MissingEmptyOrMalformedAllowlistIsBadGateway(string? host)
    {
        using var factory = new PortalFactory(new() { ["Portal:NoticeFeedAllowedHosts:0"] = host });
        using var client = await factory.SignedInClientAsync();
        factory.Upstream.Requests.Clear();
        Assert.Equal(HttpStatusCode.BadGateway, (await client.GetAsync("/bff/notices")).StatusCode);
        Assert.Empty(factory.Upstream.Requests);
    }

    [Fact]
    public async Task Notices_MalformedFeedIsBadGateway()
    {
        var client = await _factory.SignedInClientAsync();
        _factory.Upstream.NoticeFeed = "<html>maintenance</html>";
        Assert.Equal(HttpStatusCode.BadGateway, (await client.GetAsync("/bff/notices")).StatusCode);
    }
}
