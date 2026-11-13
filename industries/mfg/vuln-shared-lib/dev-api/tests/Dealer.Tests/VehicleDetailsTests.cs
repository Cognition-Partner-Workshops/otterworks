using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using Dealer.Controllers;
using Dealer.Models;

namespace Dealer.Tests;

public sealed class VehicleDetailsTests : IDisposable
{
    private readonly DealerApiFactory factory = new();
    private readonly HttpClient client;

    public VehicleDetailsTests()
    {
        client = factory.CreateClient();
        factory.Seed();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", TestTokens.Create());
    }

    [Fact]
    public async Task DetailReturnsOwnedVehicle()
    {
        var vehicle = await client.GetFromJsonAsync<Vehicle>("/api/dealer/vehicles/VIN1001");
        Assert.Equal("Atlas", vehicle!.Model);
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync("/api/dealer/vehicles/VIN2001")).StatusCode);
    }

    [Fact]
    public async Task BrowseSupportsTermSortAndPaging()
    {
        var rows = await client.GetFromJsonAsync<Vehicle[]>("/api/dealer/vehicles?term=Atl&sort=Model&size=1");
        Assert.Equal("VIN1001", Assert.Single(rows!).Vin);
        var absent = await client.GetFromJsonAsync<Vehicle[]>("/api/dealer/vehicles?term=Unknown");
        Assert.Empty(absent!);
    }

    [Fact]
    public async Task SelectionUsesOwnedVins()
    {
        var response = await client.PostAsJsonAsync("/api/dealer/vehicles/selection", new[] { "VIN1001", "VIN2001" });
        response.EnsureSuccessStatusCode();
        Assert.Equal("VIN1001", Assert.Single((await response.Content.ReadFromJsonAsync<Vehicle[]>())!).Vin);
        var empty = await client.PostAsJsonAsync("/api/dealer/vehicles/selection", Array.Empty<string>());
        Assert.Empty((await empty.Content.ReadFromJsonAsync<Vehicle[]>())!);
    }

    [Fact]
    public async Task StatusPersistsAllowedValue()
    {
        var response = await client.PutAsJsonAsync("/api/dealer/vehicles/VIN1001/status", new VehicleStatusRequest("sold"));
        Assert.Equal(HttpStatusCode.NoContent, response.StatusCode);
        Assert.Equal("sold", (await client.GetFromJsonAsync<Vehicle>("/api/dealer/vehicles/VIN1001"))!.Status);
    }

    [Fact]
    public async Task StatusRejectsUnknownValue()
    {
        var response = await client.PutAsJsonAsync("/api/dealer/vehicles/VIN1001/status", new VehicleStatusRequest("other"));
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    [Fact]
    public async Task PriceHistoryTracksChanges()
    {
        Assert.Empty((await client.GetFromJsonAsync<long[]>("/api/dealer/vehicles/VIN1001/prices"))!);
        var response = await client.PutAsJsonAsync("/api/dealer/vehicles/VIN1001/price", new VehiclePriceRequest(3100000));
        Assert.Equal(HttpStatusCode.NoContent, response.StatusCode);
        Assert.Equal(3100000, Assert.Single((await client.GetFromJsonAsync<long[]>("/api/dealer/vehicles/VIN1001/prices"))!));
    }

    [Fact]
    public async Task PriceRejectsNegativeValue()
    {
        var response = await client.PutAsJsonAsync("/api/dealer/vehicles/VIN1001/price", new VehiclePriceRequest(-1));
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    public void Dispose()
    {
        client.Dispose();
        factory.Dispose();
    }

    [Fact]
    public async Task BrowseTreatsWildcardsAsText()
    {
        var rows = await client.GetFromJsonAsync<Vehicle[]>("/api/dealer/vehicles?term=%25");
        Assert.Empty(rows!);
    }

    [Fact]
    public async Task BrowseUsesDefaultForUnknownSort()
    {
        var rows = await client.GetFromJsonAsync<Vehicle[]>("/api/dealer/vehicles?sort=other");
        Assert.Equal(new[] { "VIN1001", "VIN1002" }, rows!.Select(x => x.Vin));
    }

    [Fact]
    public async Task StatusCannotChangeOtherDealerVehicle()
    {
        var response = await client.PutAsJsonAsync("/api/dealer/vehicles/VIN2001/status", new VehicleStatusRequest("sold"));
        Assert.Equal(HttpStatusCode.NotFound, response.StatusCode);
    }
}
