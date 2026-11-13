using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;

namespace DealerPortal.Bff.Upstream;

public sealed record SignInRequest(string Email, string Password);
public sealed record SignInResponse(string AccessToken, string TokenType, int ExpiresIn, string DealerId);
public sealed record Vehicle(string Vin, string Model, int Year, string Status, long PriceCents, string ImageUrl);
public sealed record WarrantyClaim(string Id, string Vin, string Status, string Description, DateTimeOffset SubmittedAt);
public sealed record NewWarrantyClaim(string Vin, string Description);

/// <summary>Outcome of an upstream call: a value, or the status the BFF should answer with.</summary>
public sealed record UpstreamResult<T>(T? Value, HttpStatusCode Status)
{
    public bool Ok => Value is not null;
}

/// <summary>Typed client for the dealer platform API.</summary>
public sealed class DevApiClient
{
    private static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web);

    private readonly HttpClient _http;

    public DevApiClient(HttpClient http) => _http = http;

    public async Task<UpstreamResult<SignInResponse>> SignInAsync(SignInRequest request, CancellationToken ct)
    {
        using var response = await _http.PostAsJsonAsync("api/identity/signin", request, Json, ct);
        return await ReadAsync<SignInResponse>(response, ct);
    }

    public Task<UpstreamResult<List<Vehicle>>> InventoryAsync(string token, string dealerId, CancellationToken ct) =>
        GetAsync<List<Vehicle>>($"api/dealer/inventory?dealerId={Uri.EscapeDataString(dealerId)}", token, ct);

    public Task<UpstreamResult<List<WarrantyClaim>>> ClaimsAsync(string token, string dealerId, CancellationToken ct) =>
        GetAsync<List<WarrantyClaim>>($"api/warranty/claims?dealerId={Uri.EscapeDataString(dealerId)}", token, ct);

    public async Task<UpstreamResult<WarrantyClaim>> SubmitClaimAsync(string token, NewWarrantyClaim claim, CancellationToken ct)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, "api/warranty/claims")
        {
            Content = JsonContent.Create(claim, options: Json),
        };
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        using var response = await _http.SendAsync(request, ct);
        return await ReadAsync<WarrantyClaim>(response, ct);
    }

    private async Task<UpstreamResult<T>> GetAsync<T>(string path, string token, CancellationToken ct)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, path);
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        using var response = await _http.SendAsync(request, ct);
        return await ReadAsync<T>(response, ct);
    }

    private static async Task<UpstreamResult<T>> ReadAsync<T>(HttpResponseMessage response, CancellationToken ct)
    {
        if (!response.IsSuccessStatusCode)
        {
            var status = response.StatusCode switch
            {
                HttpStatusCode.Unauthorized or HttpStatusCode.Forbidden => HttpStatusCode.Unauthorized,
                HttpStatusCode.BadRequest => HttpStatusCode.BadRequest,
                HttpStatusCode.NotFound => HttpStatusCode.NotFound,
                _ => HttpStatusCode.BadGateway,
            };
            return new UpstreamResult<T>(default, status);
        }

        var value = await response.Content.ReadFromJsonAsync<T>(Json, ct);
        return new UpstreamResult<T>(value, value is null ? HttpStatusCode.BadGateway : response.StatusCode);
    }
}
