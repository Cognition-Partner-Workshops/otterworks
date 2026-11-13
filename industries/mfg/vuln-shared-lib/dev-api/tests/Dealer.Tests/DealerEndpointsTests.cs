using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using Dealer.Models;

namespace Dealer.Tests;

public sealed class DealerEndpointsTests : IDisposable
{
    private readonly DealerApiFactory factory = new();
    private readonly HttpClient client;

    public DealerEndpointsTests()
    {
        client = factory.CreateClient();
        factory.Seed();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", TestTokens.Create());
    }

    [Fact]
    public async Task InventoryReturnsDealerRows()
    {
        var rows = await client.GetFromJsonAsync<InventoryItem[]>("/api/dealer/inventory?dealerId=D-1001");
        Assert.Equal(2, rows!.Length);
        Assert.Equal("VIN1001", rows[0].Vin);
        Assert.Equal(3200000, rows[0].PriceCents);
    }

    [Fact]
    public async Task InventorySupportsPaging()
    {
        var rows = await client.GetFromJsonAsync<InventoryItem[]>("/api/dealer/inventory?dealerId=D-1001&page=3&size=1");
        Assert.Empty(rows!);
    }

    [Theory]
    [InlineData("Atlas", 1)]
    [InlineData("NoModel", 0)]
    public async Task SearchMatchesModel(string model, int count)
    {
        var rows = await client.GetFromJsonAsync<InventoryItem[]>("/api/dealer/inventory/search?dealerId=D-1001&model=" + model);
        Assert.Equal(count, rows!.Length);
    }

    [Fact]
    public async Task AgingAcceptsReportSort()
    {
        var rows = await client.GetFromJsonAsync<Vehicle[]>("/api/dealer/reports/aging?dealerId=D-1001&sort=DaysInStock%20DESC");
        Assert.Equal(new[] { "VIN1001", "VIN1002" }, rows!.Select(x => x.Vin));
    }

    [Theory]
    [InlineData("/api/dealer/inventory?dealerId=D-2001")]
    [InlineData("/api/dealer/inventory/search?dealerId=D-2001&model=Atlas")]
    [InlineData("/api/dealer/reports/aging?dealerId=D-2001")]
    public async Task InventoryRequiresDealerMembership(string route)
    {
        Assert.Equal(HttpStatusCode.Forbidden, (await client.GetAsync(route)).StatusCode);
    }

    [Fact]
    public async Task StickerDisplaysDealerNote()
    {
        var response = await client.GetAsync("/dealer/inventory/VIN1001/sticker?note=%3Cb%3EReady%3C%2Fb%3E");
        response.EnsureSuccessStatusCode();
        var body = await response.Content.ReadAsStringAsync();
        Assert.Contains("<b>Ready</b>", body);
        Assert.Contains("Atlas", body);
    }

    [Fact]
    public async Task StickerReturnsNotFoundForOtherDealer()
    {
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync("/dealer/inventory/VIN2001/sticker")).StatusCode);
    }

    [Fact]
    public async Task ExportCanBeReadByName()
    {
        var response = await client.GetAsync("/api/dealer/exports/files?name=stock.csv");
        response.EnsureSuccessStatusCode();
        Assert.Contains("VIN1001", await response.Content.ReadAsStringAsync());
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync("/api/dealer/exports/files?name=absent.csv")).StatusCode);
    }

    [Fact]
    public async Task ExportLinkRoundTrip()
    {
        var created = await client.PostAsJsonAsync("/api/dealer/exports/links", new { fileName = "stock.csv" });
        created.EnsureSuccessStatusCode();
        var link = await created.Content.ReadFromJsonAsync<JsonElement>();
        var path = $"/api/dealer/exports/download?name=stock.csv&expires={link.GetProperty("expires").GetInt64()}&signature={link.GetProperty("signature").GetString()}";
        var downloaded = await client.GetAsync(path);
        downloaded.EnsureSuccessStatusCode();
        Assert.Contains("VIN1001", await downloaded.Content.ReadAsStringAsync());
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.GetAsync(path + "a")).StatusCode);
    }

    [Fact]
    public async Task ImageProxyUsesImageTransport()
    {
        var response = await client.GetAsync("/api/dealer/images/proxy?url=https%3A%2F%2Fimages.dealer.example%2Fstock.png");
        response.EnsureSuccessStatusCode();
        Assert.Equal("image/png", response.Content.Headers.ContentType!.MediaType);
        Assert.Equal("image-content", await response.Content.ReadAsStringAsync());
        Assert.Equal("images.dealer.example", factory.Transport.RequestedUri!.Host);
    }

    [Fact]
    public async Task ImageProxyReportsUpstreamFailure()
    {
        factory.Transport.Status = HttpStatusCode.NotFound;
        Assert.Equal(HttpStatusCode.BadGateway, (await client.GetAsync("/api/dealer/images/proxy?url=https://images.dealer.example/absent")).StatusCode);
    }

    [Fact]
    public async Task BulletinRefreshStoresRows()
    {
        var response = await client.PostAsync("/api/dealer/bulletins/refresh", null);
        response.EnsureSuccessStatusCode();
        Assert.Equal(1, factory.BulletinCount());
    }

    [Fact]
    public async Task BulletinRefreshAcceptsEmptyList()
    {
        factory.Transport.BulletinBody = "[]";
        var response = await client.PostAsync("/api/dealer/bulletins/refresh", null);
        Assert.Equal(0, (await response.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("stored").GetInt32());
    }

    [Fact]
    public async Task BulletinRefreshReportsUpstreamFailure()
    {
        factory.Transport.Status = HttpStatusCode.ServiceUnavailable;
        Assert.Equal(HttpStatusCode.BadGateway, (await client.PostAsync("/api/dealer/bulletins/refresh", null)).StatusCode);
    }

    [Theory]
    [InlineData("")]
    [InlineData("other")]
    public async Task InventoryRequiresBearerToken(string token)
    {
        client.DefaultRequestHeaders.Authorization = token == "" ? null : new AuthenticationHeaderValue("Bearer", token);
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.GetAsync("/api/dealer/inventory?dealerId=D-1001")).StatusCode);
    }

    [Fact]
    public async Task InventoryRejectsExpiredToken()
    {
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", TestTokens.Create(1));
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.GetAsync("/api/dealer/inventory?dealerId=D-1001")).StatusCode);
    }

    public void Dispose()
    {
        client.Dispose();
        factory.Dispose();
    }
}
