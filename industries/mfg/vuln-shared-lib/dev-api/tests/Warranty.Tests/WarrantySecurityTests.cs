using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text;
using Warranty.Models;

namespace Warranty.Tests;

public sealed class WarrantySecurityTests : IDisposable
{
    private readonly WarrantyApiFactory factory = new();
    private readonly HttpClient client;

    public WarrantySecurityTests()
    {
        client = factory.CreateClient();
        factory.Seed();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", TestTokens.Create());
    }

    [Fact]
    [Trait("Category", "Security")]
    public async Task SearchTreatsSqlPayloadAsLiteral()
    {
        var status = Uri.EscapeDataString("submitted' OR 1=1 --");
        var rows = await client.GetFromJsonAsync<ClaimResponse[]>($"/api/warranty/claims/search?dealerId=D-1001&status={status}");
        Assert.Empty(rows!);
    }

    [Theory]
    [Trait("Category", "Security")]
    [InlineData("{\"$type\":\"Warranty.Models.ClaimImportBatch, Warranty\",\"Items\":[]}")]
    [InlineData("{\"Items\":[{\"$type\":\"Warranty.Models.RepairClaimItem, Warranty\",\"Vin\":\"VIN1003\",\"Description\":\"Repair\"}]}")]
    public async Task ImportRejectsTypeMetadata(string json)
    {
        var response = await Import(json);
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.Single((await client.GetFromJsonAsync<ClaimResponse[]>("/api/warranty/claims?dealerId=D-1001"))!);
    }

    [Theory]
    [InlineData("{\"Items\":[null]}")]
    [InlineData("{\"Items\":null}")]
    [InlineData("{\"Items\":[{\"Vin\":\"VIN1003\",\"Description\":\"\"}]}")]
    public async Task ImportRejectsInvalidItems(string json)
    {
        Assert.Equal(HttpStatusCode.BadRequest, (await Import(json)).StatusCode);
    }

    [Fact]
    public async Task ImportAcceptsConcreteItems()
    {
        var response = await Import("{\"Items\":[{\"Vin\":\"VIN1003\",\"Description\":\"Repair\",\"RepairCode\":\"R-10\"}]}");
        response.EnsureSuccessStatusCode();
        Assert.Equal(2, (await client.GetFromJsonAsync<ClaimResponse[]>("/api/warranty/claims?dealerId=D-1001"))!.Length);
    }

    [Theory]
    [Trait("Category", "Security")]
    [InlineData("../outside.txt")]
    [InlineData("..\\outside.txt")]
    [InlineData("/etc/passwd")]
    public async Task DownloadRejectsTraversal(string name)
    {
        File.WriteAllText(Path.Combine(factory.AttachmentRoot, "outside.txt"), "Outside attachment root");
        var response = await client.GetAsync($"/api/warranty/claims/1/attachments/download?name={Uri.EscapeDataString(name)}");
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    [Fact]
    public async Task DownloadMissingFileReturnsNotFound()
    {
        var response = await client.GetAsync("/api/warranty/claims/1/attachments/download?name=absent.txt");
        Assert.Equal(HttpStatusCode.NotFound, response.StatusCode);
    }

    private Task<HttpResponseMessage> Import(string json) => client.PostAsync("/api/warranty/claims/import",
        new StringContent(json, Encoding.UTF8, "application/json"));

    public void Dispose()
    {
        client.Dispose();
        factory.Dispose();
    }
}
