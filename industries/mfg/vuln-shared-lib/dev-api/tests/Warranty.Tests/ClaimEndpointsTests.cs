using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using Newtonsoft.Json;
using Warranty.Models;

namespace Warranty.Tests;

public sealed class ClaimEndpointsTests : IDisposable
{
    private readonly WarrantyApiFactory factory = new();
    private readonly HttpClient client;

    public ClaimEndpointsTests()
    {
        client = factory.CreateClient();
        factory.Seed();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", TestTokens.Create());
    }

    [Fact]
    public async Task ListReturnsDealerClaims()
    {
        var rows = await client.GetFromJsonAsync<ClaimResponse[]>("/api/warranty/claims?dealerId=D-1001");
        Assert.Single(rows!);
        Assert.Equal("VIN1001", rows![0].Vin);
        Assert.Equal("submitted", rows[0].Status);
    }

    [Fact]
    public async Task SearchReturnsMatchingStatus()
    {
        var rows = await client.GetFromJsonAsync<ClaimResponse[]>("/api/warranty/claims/search?dealerId=D-1001&status=submitted");
        Assert.Single(rows!);
        var absent = await client.GetFromJsonAsync<ClaimResponse[]>("/api/warranty/claims/search?dealerId=D-1001&status=approved");
        Assert.Empty(absent!);
    }

    [Fact]
    public async Task CreateUsesTokenDealer()
    {
        var response = await client.PostAsJsonAsync("/api/warranty/claims", new CreateClaimRequest("VIN1003", "Mirror adjustment"));
        Assert.Equal(HttpStatusCode.Created, response.StatusCode);
        var claim = await response.Content.ReadFromJsonAsync<ClaimResponse>();
        var detail = await client.GetFromJsonAsync<ClaimResponse>(response.Headers.Location);
        Assert.Equal(claim, detail);
    }

    [Theory]
    [InlineData("", "Door")]
    [InlineData("VIN1001", "")]
    public async Task CreateValidatesRequest(string vin, string description)
    {
        var response = await client.PostAsJsonAsync("/api/warranty/claims", new CreateClaimRequest(vin, description));
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    [Fact]
    public async Task StatusAndNotesAreStored()
    {
        var changed = await client.PutAsJsonAsync("/api/warranty/claims/1/status", new ClaimStatusRequest("reviewing"));
        changed.EnsureSuccessStatusCode();
        Assert.Equal("reviewing", (await changed.Content.ReadFromJsonAsync<ClaimResponse>())!.Status);
        var note = await client.PostAsJsonAsync("/api/warranty/claims/1/notes", new ClaimNoteRequest("Receipt checked"));
        Assert.Equal(HttpStatusCode.Created, note.StatusCode);
        Assert.Equal("Receipt checked", (await note.Content.ReadFromJsonAsync<ClaimNote>())!.Text);
    }

    [Fact]
    public async Task StatusValidatesValues()
    {
        var response = await client.PutAsJsonAsync("/api/warranty/claims/1/status", new ClaimStatusRequest("other"));
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    [Theory]
    [InlineData("/api/warranty/claims/2")]
    [InlineData("/api/warranty/claims/99")]
    [InlineData("/api/warranty/claims/2/attachments")]
    public async Task DetailRequiresOwnedClaim(string route)
    {
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync(route)).StatusCode);
    }

    [Fact]
    public async Task ListRequiresMatchingDealer()
    {
        var response = await client.GetAsync("/api/warranty/claims?dealerId=D-2001");
        Assert.Equal(HttpStatusCode.Forbidden, response.StatusCode);
    }

    [Fact]
    public async Task ClaimImportReadsRepairAndPartsItems()
    {
        var batch = new ClaimImportBatch
        {
            Items =
            [
                new RepairClaimItem { Vin = "VIN1001", Description = "Latch repair", RepairCode = "R-10" },
                new PartsClaimItem { Vin = "VIN1002", Description = "Mirror glass", PartNumber = "P-20" }
            ]
        };
        var json = JsonConvert.SerializeObject(batch, new JsonSerializerSettings { TypeNameHandling = TypeNameHandling.All });
        var response = await client.PostAsync("/api/warranty/claims/import", new StringContent(json, Encoding.UTF8, "application/json"));
        response.EnsureSuccessStatusCode();
        Assert.Equal(2, (await response.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("imported").GetInt32());
    }

    [Theory]
    [InlineData("{}", 0)]
    [InlineData("{\"Items\":[]}", 0)]
    public async Task ClaimImportAcceptsEmptyBatch(string json, int expected)
    {
        var response = await client.PostAsync("/api/warranty/claims/import", new StringContent(json, Encoding.UTF8, "application/json"));
        response.EnsureSuccessStatusCode();
        Assert.Equal(expected, (await response.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("imported").GetInt32());
    }

    [Theory]
    [InlineData("null")]
    [InlineData("{")]
    public async Task ClaimImportReportsUnreadableBody(string json)
    {
        var response = await client.PostAsync("/api/warranty/claims/import", new StringContent(json, Encoding.UTF8, "application/json"));
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    [Fact]
    public async Task AttachmentsListPreviewAndDownload()
    {
        var files = await client.GetFromJsonAsync<AttachmentResponse[]>("/api/warranty/claims/1/attachments");
        Assert.Equal("receipt.txt", Assert.Single(files!).Name);
        foreach (var action in new[] { "preview", "download" })
        {
            var response = await client.GetAsync($"/api/warranty/claims/1/attachments/{action}?name=receipt.txt");
            response.EnsureSuccessStatusCode();
            Assert.Equal("Parts receipt", await response.Content.ReadAsStringAsync());
        }
    }

    [Fact]
    public async Task AttachmentsReturnEmptyListForNewClaim()
    {
        var created = await client.PostAsJsonAsync("/api/warranty/claims", new CreateClaimRequest("VIN1004", "Trim"));
        var claim = await created.Content.ReadFromJsonAsync<ClaimResponse>();
        var files = await client.GetFromJsonAsync<AttachmentResponse[]>($"/api/warranty/claims/{claim!.Id}/attachments");
        Assert.Empty(files!);
    }

    [Fact]
    public async Task PreviewReportsMissingFile()
    {
        var response = await client.GetAsync("/api/warranty/claims/1/attachments/preview?name=absent.txt");
        Assert.Equal(HttpStatusCode.NotFound, response.StatusCode);
    }

    [Fact]
    public async Task ClaimsRequireToken()
    {
        client.DefaultRequestHeaders.Authorization = null;
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.GetAsync("/api/warranty/claims?dealerId=D-1001")).StatusCode);
    }

    public void Dispose()
    {
        client.Dispose();
        factory.Dispose();
    }

    [Fact]
    public async Task ClaimImportValidatesEachItem()
    {
        var batch = new ClaimImportBatch
        {
            Items = [new RepairClaimItem { Vin = "", Description = "Latch repair", RepairCode = "R-10" }]
        };
        var json = JsonConvert.SerializeObject(batch, new JsonSerializerSettings { TypeNameHandling = TypeNameHandling.All });
        var response = await client.PostAsync("/api/warranty/claims/import",
            new StringContent(json, Encoding.UTF8, "application/json"));
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    [Fact]
    public async Task NoteRequiresText()
    {
        var response = await client.PostAsJsonAsync("/api/warranty/claims/1/notes", new ClaimNoteRequest(""));
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }
}
