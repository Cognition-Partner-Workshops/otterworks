using System.Net;
using System.Net.Http.Headers;

namespace Payments.Tests;

[Collection("Payments transport")]
public sealed class FetchPolicyRegressionTests
{
    [Theory]
    [Trait("Category","Security")]
    [InlineData(false)]
    [InlineData(true)]
    public async Task BlockedHostOrRedirect_IsRefusedWithoutSending(bool redirect)
    {
        using var factory = new PaymentsApiFactory();
        if (redirect) factory.Transport.RedirectTo = new Uri("https://blocked.example/");
        else factory.RemittanceUrl = "https://blocked.example/";
        using var client = factory.CreateClient();
        factory.Seed();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", TestTokens.Create());
        var response = await client.PostAsync("/api/payments/remittance/pull", null);
        Assert.Equal(HttpStatusCode.BadGateway, response.StatusCode);
        Assert.DoesNotContain(factory.Transport.Requests, uri => uri.Host == "blocked.example");
        Assert.Equal(redirect ? 1 : 0, factory.Transport.Requests.Count);
    }
}

[CollectionDefinition("Payments transport", DisableParallelization = true)]
public sealed class PaymentsTransportCollection { }
