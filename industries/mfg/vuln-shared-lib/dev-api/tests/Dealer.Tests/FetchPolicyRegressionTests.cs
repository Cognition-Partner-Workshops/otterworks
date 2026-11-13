using System.Net;
using System.Net.Http.Headers;

namespace Dealer.Tests;

public sealed class FetchPolicyRegressionTests
{
    [Theory]
    [Trait("Category","Security")]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("https://malformed.example/")]
    public async Task MissingEmptyOrMalformedAllowlist_IsBadGatewayWithoutSending(string? host)
    {
        using var factory = new DealerApiFactory { BulletinAllowedHost = host };
        using var client = factory.CreateClient();
        factory.Seed();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", TestTokens.Create());
        var response = await client.PostAsync("/api/dealer/bulletins/refresh", null);
        Assert.Equal(HttpStatusCode.BadGateway, response.StatusCode);
        Assert.Empty(factory.Transport.Requests);
    }

    [Theory]
    [Trait("Category","Security")]
    [InlineData(false)]
    [InlineData(true)]
    public async Task BlockedHostOrRedirect_IsRefusedWithoutSending(bool redirect)
    {
        using var factory = new DealerApiFactory();
        if (redirect) factory.Transport.RedirectTo = new Uri("https://blocked.example/");
        else factory.BulletinUrl = "https://blocked.example/";
        using var client = factory.CreateClient();
        factory.Seed();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", TestTokens.Create());
        var response = await client.PostAsync("/api/dealer/bulletins/refresh", null);
        Assert.Equal(HttpStatusCode.BadGateway, response.StatusCode);
        Assert.DoesNotContain(factory.Transport.Requests, uri => uri.Host == "blocked.example");
        Assert.Equal(redirect ? 1 : 0, factory.Transport.Requests.Count);
    }
}
