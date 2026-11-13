using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using Dealer.Models;

namespace Dealer.Tests;

public sealed class DealerSecurityTests : IDisposable
{
    private readonly DealerApiFactory factory = new();
    private readonly HttpClient client;

    public DealerSecurityTests()
    {
        client = factory.CreateClient();
        factory.Seed();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", TestTokens.Create());
    }

    [Theory]
    [InlineData("' OR 1=1 --")]
    [InlineData("%")]
    [InlineData("_")]
    public async Task SearchTreatsModelAsLiteral(string model)
    {
        var rows = await client.GetFromJsonAsync<InventoryItem[]>(
            "/api/dealer/inventory/search?dealerId=D-1001&model=" + Uri.EscapeDataString(model));
        Assert.Empty(rows!);
    }

    [Theory]
    [InlineData("CASE WHEN Vin='VIN1002' THEN 0 ELSE 1 END")]
    [InlineData("DaysInStock DESC; SELECT 1")]
    [InlineData("unknown")]
    [InlineData("")]
    public async Task AgingRejectsSqlSortExpressions(string sort)
    {
        var rows = await client.GetFromJsonAsync<Vehicle[]>(
            "/api/dealer/reports/aging?dealerId=D-1001&sort=" + Uri.EscapeDataString(sort));
        Assert.Equal(new[] { "VIN1001", "VIN1002" }, rows!.Select(row => row.Vin));
    }

    [Theory]
    [InlineData("DaysInStock ASC", "VIN1002")]
    [InlineData("DaysInStock DESC", "VIN1001")]
    [InlineData("Model", "VIN1001")]
    public async Task AgingPreservesAllowedSorts(string sort, string firstVin)
    {
        var rows = await client.GetFromJsonAsync<Vehicle[]>(
            "/api/dealer/reports/aging?dealerId=D-1001&sort=" + Uri.EscapeDataString(sort));
        Assert.Equal(firstVin, rows![0].Vin);
    }

    [Theory]
    [InlineData("<script>alert(1)</script>")]
    [InlineData("<img src=x onerror=alert(1)>")]
    public async Task StickerEncodesUntrustedNote(string note)
    {
        var response = await client.GetAsync("/dealer/inventory/VIN1001/sticker?note=" + Uri.EscapeDataString(note));
        response.EnsureSuccessStatusCode();
        var body = await response.Content.ReadAsStringAsync();
        Assert.DoesNotContain(note, body);
        Assert.Contains("&lt;", body);
    }

    [Fact]
    public async Task StickerAcceptsEmptyNote()
    {
        var response = await client.GetAsync("/dealer/inventory/VIN1001/sticker");
        response.EnsureSuccessStatusCode();
        Assert.Contains("Atlas", await response.Content.ReadAsStringAsync());
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public async Task ExportRejectsFilesOutsideRoot(bool absolute)
    {
        var outside = factory.ExportRoot + "-outside.csv";
        await File.WriteAllTextAsync(outside, "private-export");
        try
        {
            var name = absolute ? outside : "../" + Path.GetFileName(outside);
            var response = await client.GetAsync("/api/dealer/exports/files?name=" + Uri.EscapeDataString(name));
            Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        }
        finally { File.Delete(outside); }
    }

    [Fact]
    public async Task ExportRejectsSymbolicLink()
    {
        var outside = factory.ExportRoot + "-outside.csv";
        await File.WriteAllTextAsync(outside, "private-export");
        try
        {
            File.CreateSymbolicLink(Path.Combine(factory.ExportRoot, "link.csv"), outside);
            Assert.Equal(HttpStatusCode.BadRequest,
                (await client.GetAsync("/api/dealer/exports/files?name=link.csv")).StatusCode);
        }
        finally { File.Delete(outside); }
    }

    [Theory]
    [InlineData("http://images.dealer.example/stock.png")]
    [InlineData("https://unapproved.example/stock.png")]
    [InlineData("https://images.dealer.example.unapproved.example/stock.png")]
    [InlineData("https://images.dealer.example:8443/stock.png")]
    [InlineData("https://user@images.dealer.example/stock.png")]
    [InlineData("not-a-url")]
    [InlineData("")]
    public async Task ImageProxyRejectsUnapprovedUrlsWithoutFetching(string url)
    {
        var response = await client.GetAsync("/api/dealer/images/proxy?url=" + Uri.EscapeDataString(url));
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.Null(factory.Transport.RequestedUri);
    }

    [Fact]
    public async Task ImageProxyRejectsRedirectResponse()
    {
        factory.Transport.Status = HttpStatusCode.Redirect;
        Assert.Equal(HttpStatusCode.BadGateway,
            (await client.GetAsync("/api/dealer/images/proxy?url=https://images.dealer.example/redirect")).StatusCode);
    }

    public void Dispose()
    {
        client.Dispose();
        factory.Dispose();
    }
}
