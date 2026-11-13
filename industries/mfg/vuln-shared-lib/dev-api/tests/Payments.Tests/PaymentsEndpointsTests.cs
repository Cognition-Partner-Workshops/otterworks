using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using Newtonsoft.Json;
using Payments.Models;
using Payments.Services;

namespace Payments.Tests;

[Collection("Payments transport")]
public sealed class PaymentsEndpointsTests : IDisposable
{
    private readonly PaymentsApiFactory factory = new();
    private readonly HttpClient client;

    public PaymentsEndpointsTests()
    {
        client = factory.CreateClient();
        factory.Seed();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", TestTokens.Create());
    }

    [Fact]
    [Trait("Category","Security")]
    public async Task SettlementsListOnlyTokenDealer()
    {
        var rows = await client.GetFromJsonAsync<Settlement[]>("/api/payments/settlements");
        Assert.Equal("ST-1001", Assert.Single(rows!).Reference);
    }

    [Fact]
    public async Task CreateSettlementAndRejectDuplicate()
    {
        var request = new CreateSettlementRequest("ST-1003", 2000);
        var response = await client.PostAsJsonAsync("/api/payments/settlements", request);
        Assert.Equal(HttpStatusCode.Created, response.StatusCode);
        Assert.Equal(2000, (await response.Content.ReadFromJsonAsync<Settlement>())!.AmountCents);
        var duplicate = await client.PostAsJsonAsync("/api/payments/settlements", request);
        Assert.Equal(HttpStatusCode.Conflict, duplicate.StatusCode);
    }

    [Fact]
    public async Task CreateSettlementValidatesAmount()
    {
        var response = await client.PostAsJsonAsync("/api/payments/settlements", new CreateSettlementRequest("", 0));
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    [Fact]
    public async Task SettlementImportIncludesFeeAdjustment()
    {
        var batch = new SettlementBatch
        {
            Items =
            [
                new SettlementImportItem
                {
                    Reference = "ST-1003",
                    AmountCents = 5000,
                    Adjustment = new FeeAdjustment { AmountCents = -100, FeeCode = "processing" }
                }
            ]
        };
        var json = JsonConvert.SerializeObject(batch, new JsonSerializerSettings { TypeNameHandling = TypeNameHandling.Auto });
        var response = await client.PostAsync("/api/payments/settlements/import",
            new StringContent(json, Encoding.UTF8, "application/json"));
        response.EnsureSuccessStatusCode();
        var rows = await client.GetFromJsonAsync<Settlement[]>("/api/payments/settlements");
        Assert.Equal(4900, rows!.Single(x => x.Reference == "ST-1003").AmountCents);
    }

    [Theory]
    [InlineData("{}")]
    [InlineData("{\"Items\":[]}")]
    public async Task SettlementImportAcceptsEmptyBatch(string json)
    {
        var response = await client.PostAsync("/api/payments/settlements/import", new StringContent(json, Encoding.UTF8, "application/json"));
        response.EnsureSuccessStatusCode();
        Assert.Equal(0, (await response.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("imported").GetInt32());
    }

    [Theory]
    [InlineData("null")]
    [InlineData("{")]
    public async Task SettlementImportReportsInvalidBody(string json)
    {
        var response = await client.PostAsync("/api/payments/settlements/import", new StringContent(json, Encoding.UTF8, "application/json"));
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    [Fact]
    public async Task RefundReturnsCreatedRecord()
    {
        var response = await client.PostAsJsonAsync("/api/payments/refunds", new RefundRequest(1, 500, "Unused part"));
        Assert.Equal(HttpStatusCode.Created, response.StatusCode);
        var refund = await response.Content.ReadFromJsonAsync<Refund>();
        Assert.Equal(500, refund!.AmountCents);
        var detail = await client.GetFromJsonAsync<Refund>(response.Headers.Location);
        Assert.Equal(refund.Id, detail!.Id);
    }

    [Fact]
    public async Task RefundCannotExceedRemainingAmount()
    {
        var response = await client.PostAsJsonAsync("/api/payments/refunds", new RefundRequest(1, 9500, "Return"));
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    [Fact]
    [Trait("Category","Security")]
    public async Task RefundCreationRequiresOwnedSettlement()
    {
        var response = await client.PostAsJsonAsync("/api/payments/refunds", new RefundRequest(2, 500, "Return"));
        Assert.Equal(HttpStatusCode.NotFound, response.StatusCode);
    }

    [Fact]
    [Trait("Category","Security")]
    public async Task RefundDetailCanBeReadWithoutSession()
    {
        client.DefaultRequestHeaders.Authorization = null;
        var refund = await client.GetFromJsonAsync<Refund>("/api/payments/refunds/1");
        Assert.Equal("Parts return", refund!.Reason);
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync("/api/payments/refunds/999")).StatusCode);
    }

    [Fact]
    [Trait("Category","Security")]
    public async Task ProcessorCallbackStoresStatusAndSignedEvent()
    {
        client.DefaultRequestHeaders.Add("X-Processor-Secret", "vsl-synthetic-processor-api-secret-remittance");
        var response = await client.PostAsJsonAsync("/api/payments/processor/callback", new ProcessorCallbackRequest(1, "paid"));
        Assert.Equal(HttpStatusCode.NoContent, response.StatusCode);
        var rows = await client.GetFromJsonAsync<Settlement[]>("/api/payments/settlements");
        Assert.Equal("paid", rows!.Single().Status);
        var entry = Assert.Single((await client.GetFromJsonAsync<WebhookEvent[]>("/api/payments/webhooks/events"))!);
        Assert.True(new WebhookSigner(TestConfiguration.SyntheticSigning.Provider).Verify(entry.Body, entry.Signature));
    }

    [Fact]
    [Trait("Category","Security")]
    public async Task ProcessorCallbackRequiresSecret()
    {
        var response = await client.PostAsJsonAsync("/api/payments/processor/callback", new ProcessorCallbackRequest(1, "paid"));
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    [Trait("Category","Security")]
    public async Task WebhookTestPostsSignedSample()
    {
        var response = await client.PostAsJsonAsync("/api/payments/webhooks/test", new WebhookTestRequest("https://subscriber.dealer.example/events"));
        response.EnsureSuccessStatusCode();
        Assert.Equal("subscriber.dealer.example", factory.Transport.Destination!.Host);
        Assert.True(new WebhookSigner(TestConfiguration.SyntheticSigning.Provider).Verify(factory.Transport.Body!, factory.Transport.Signature!));
    }

    [Fact]
    public async Task WebhookTestReportsUpstreamFailure()
    {
        factory.Transport.Status = HttpStatusCode.ServiceUnavailable;
        var response = await client.PostAsJsonAsync("/api/payments/webhooks/test", new WebhookTestRequest("https://subscriber.dealer.example/events"));
        Assert.Equal(HttpStatusCode.BadGateway, response.StatusCode);
    }

    [Fact]
    public async Task WebhookTestValidatesAddress()
    {
        var response = await client.PostAsJsonAsync("/api/payments/webhooks/test", new WebhookTestRequest(""));
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    [Fact]
    public async Task RemittancePullStoresStatement()
    {
        var response = await client.PostAsync("/api/payments/remittance/pull", null);
        response.EnsureSuccessStatusCode();
        var rows = await client.GetFromJsonAsync<Settlement[]>("/api/payments/settlements");
        Assert.Contains(rows!, row => row.Reference == "REM-1001");
    }

    [Fact]
    public async Task RemittancePullAcceptsEmptyStatement()
    {
        factory.Transport.Statement = "[]";
        var response = await client.PostAsync("/api/payments/remittance/pull", null);
        response.EnsureSuccessStatusCode();
        Assert.Equal(0, (await response.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("imported").GetInt32());
    }

    [Fact]
    public async Task RemittancePullReportsUpstreamFailure()
    {
        factory.Transport.Status = HttpStatusCode.ServiceUnavailable;
        Assert.Equal(HttpStatusCode.BadGateway, (await client.PostAsync("/api/payments/remittance/pull", null)).StatusCode);
    }

    [Theory]
    [Trait("Category","Security")]
    [InlineData("/api/payments/settlements")]
    [InlineData("/api/payments/refunds")]
    [InlineData("/api/payments/webhooks/events")]
    public async Task ListsRequireSession(string route)
    {
        client.DefaultRequestHeaders.Authorization = null;
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.GetAsync(route)).StatusCode);
    }

    [Fact]
    [Trait("Category","Security")]
    public async Task PaymentsRoleIsRequired()
    {
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", TestTokens.Create(roles: ["dealer"]));
        Assert.Equal(HttpStatusCode.Forbidden, (await client.GetAsync("/api/payments/settlements")).StatusCode);
    }

    public void Dispose()
    {
        client.Dispose();
        factory.Dispose();
    }

    [Fact]
    [Trait("Category","Security")]
    public async Task ProcessorCallbackRejectsDifferentSecret()
    {
        client.DefaultRequestHeaders.Add("X-Processor-Secret", "vsl-synthetic-other-secret");
        var response = await client.PostAsJsonAsync("/api/payments/processor/callback", new ProcessorCallbackRequest(1, "paid"));
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    [Trait("Category","Security")]
    public async Task ExpiredTokenCannotReadSettlements()
    {
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", TestTokens.Create(expires: 1));
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.GetAsync("/api/payments/settlements")).StatusCode);
    }

    [Fact]
    [Trait("Category","Security")]
    public async Task OtherDealerStartsWithNoEvents()
    {
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", TestTokens.Create(dealer: "D-2001"));
        Assert.Empty((await client.GetFromJsonAsync<WebhookEvent[]>("/api/payments/webhooks/events"))!);
    }

    [Fact]
    public async Task RemittancePullReportsUnreadableStatement()
    {
        factory.Transport.Statement = "{";
        var response = await client.PostAsync("/api/payments/remittance/pull", null);
        Assert.Equal(HttpStatusCode.BadGateway, response.StatusCode);
    }
}
