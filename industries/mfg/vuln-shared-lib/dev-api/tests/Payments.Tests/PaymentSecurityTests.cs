using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text;
using Newtonsoft.Json;
using Payments.Models;

namespace Payments.Tests;

public sealed class PaymentSecurityTests
{
    [Fact]
    [Trait("Category","Security")]
    public async Task ImportRejectsUnknownAdjustmentWithoutConstructingIt()
    {
        using var factory = new PaymentsApiFactory();
        using var client = factory.CreateClient();
        factory.Seed();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", TestTokens.Create());
        var type = typeof(SideEffectAdjustment).AssemblyQualifiedName;
        var json = """{"Items":[{"Reference":"SEC-1","AmountCents":100,"Adjustment":{"$type":TYPE,"AmountCents":1}}]}"""
            .Replace("TYPE", JsonConvert.SerializeObject(type));
        SideEffectAdjustment.Constructed = false;
        var response = await client.PostAsync("/api/payments/settlements/import", new StringContent(json, Encoding.UTF8, "application/json"));
        Assert.False(SideEffectAdjustment.Constructed);
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    [Theory]
    [Trait("Category","Security")]
    [InlineData("http://169.254.169.254/latest/meta-data")]
    [InlineData("https://127.0.0.1/")]
    [InlineData("https://10.0.0.5/")]
    [InlineData("https://[::1]/")]
    [InlineData("https://198.18.0.1/")]
    public async Task WebhookRejectsUnsafeDestination(string url)
    {
        using var factory = new PaymentsApiFactory();
        using var client = factory.CreateClient();
        factory.Seed();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", TestTokens.Create());
        var response = await client.PostAsJsonAsync("/api/payments/webhooks/test", new WebhookTestRequest(url));
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.Null(factory.Transport.Destination);
    }

    [Theory]
    [Trait("Category","Security")]
    [InlineData(null)]
    [InlineData("vsl-synthetic-processor-api-secret-remittance")]
    [InlineData("synthetic-wrong")]
    public async Task DefaultProcessorRejectsSecret(string? secret)
    {
        using var factory = new PaymentsApiFactory();
        using var client = factory.CreateClient();
        factory.Seed();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", TestTokens.Create());
        if (secret is not null) client.DefaultRequestHeaders.Add("X-Processor-Secret", secret);
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.PostAsJsonAsync("/api/payments/processor/callback", new ProcessorCallbackRequest(1, "paid"))).StatusCode);
    }

    [Theory]
    [Trait("Category","Security")]
    [InlineData(1, HttpStatusCode.OK)]
    [InlineData(2, HttpStatusCode.NotFound)]
    [InlineData(999, HttpStatusCode.NotFound)]
    public async Task RefundDetailIsDealerScoped(int id, HttpStatusCode expected)
    {
        using var factory = new PaymentsApiFactory();
        using var client = factory.CreateClient();
        factory.Seed();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", TestTokens.Create());
        Assert.Equal(expected, (await client.GetAsync($"/api/payments/refunds/{id}")).StatusCode);
    }
}

public sealed class SideEffectAdjustment : SettlementAdjustment
{
    public static bool Constructed;
    public SideEffectAdjustment() => Constructed = true;
}
