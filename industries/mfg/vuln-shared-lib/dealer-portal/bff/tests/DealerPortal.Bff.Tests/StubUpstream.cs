using System.Net;
using System.Text;
using System.Text.Json;

namespace DealerPortal.Bff.Tests;

/// <summary>In-memory stand-in for the dealer platform API and the OEM notice feed.</summary>
public sealed class StubUpstream : HttpMessageHandler
{
    public const string Email = "dealer-ops@dealer.example";
    public const string DealerId = "D-1001";
    public const string AccessToken =
        "v1.eyJzdWIiOiJkZWFsZXItb3BzQGRlYWxlci5leGFtcGxlIiwiZGVhbGVyIjoiRC0xMDAxIiwicm9sZXMiOlsiZGVhbGVyIl0sImlhdCI6MTc5ODc2MTYwMCwiZXhwIjoxNzk4NzY1MjAwfQ.tsR_nbfw6TFkFEydowMEG_yXhQQgMO3oYDFVNkxeA1s";

    private static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web);

    public List<HttpRequestMessage> Requests { get; } = [];
    public List<string> Bodies { get; } = [];
    public HttpStatusCode? ForceStatus { get; set; }
    public Uri? NoticeRedirect { get; set; }
    public string NoticeFeed { get; set; } = JsonSerializer.Serialize(new[]
    {
        new { id = "N-1", title = "Brake hose inspection", severity = "critical", publishedAt = "2026-02-01T12:00:00Z", body = "Inspect before delivery." },
    }, Json);

    public static readonly object[] Inventory =
    [
        new { vin = "1VSLA0000AA000001", model = "Ranger LT", year = 2026, status = "AVAILABLE", priceCents = 3899000, imageUrl = "https://img.dealer.example/1.png" },
        new { vin = "1VSLA0000AA000002", model = "Harbor XL", year = 2025, status = "SOLD", priceCents = 4525000, imageUrl = "https://img.dealer.example/2.png" },
    ];

    protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        Requests.Add(request);
        var body = request.Content is null ? string.Empty : await request.Content.ReadAsStringAsync(cancellationToken);
        Bodies.Add(body);

        if (ForceStatus is { } forced)
        {
            return new HttpResponseMessage(forced);
        }

        var path = request.RequestUri!.AbsolutePath;
        if (path.EndsWith("/dealer-notices.json", StringComparison.Ordinal))
        {
            if (NoticeRedirect is not null) return new HttpResponseMessage(HttpStatusCode.Found) { Headers = { Location = NoticeRedirect } };
            return Respond(HttpStatusCode.OK, NoticeFeed);
        }

        if (path == "/api/identity/signin")
        {
            using var doc = JsonDocument.Parse(body);
            return doc.RootElement.GetProperty("email").GetString() == Email
                ? Respond(HttpStatusCode.OK, new { accessToken = AccessToken, tokenType = "Bearer", expiresIn = 3600, dealerId = DealerId })
                : new HttpResponseMessage(HttpStatusCode.Unauthorized);
        }

        if (request.Headers.Authorization?.ToString() != $"Bearer {AccessToken}")
        {
            return new HttpResponseMessage(HttpStatusCode.Unauthorized);
        }

        return (request.Method.Method, path) switch
        {
            ("GET", "/api/dealer/inventory") => Respond(HttpStatusCode.OK, Inventory),
            ("GET", "/api/warranty/claims") => Respond(HttpStatusCode.OK, new[]
            {
                new { id = "WC-1", vin = "1VSLA0000AA000001", status = "SUBMITTED", description = "Rattle at idle", submittedAt = "2026-02-11T15:30:00Z" },
            }),
            ("POST", "/api/warranty/claims") => CreateClaim(body),
            _ => new HttpResponseMessage(HttpStatusCode.NotFound),
        };
    }

    private static HttpResponseMessage CreateClaim(string body)
    {
        using var doc = JsonDocument.Parse(body);
        return Respond(HttpStatusCode.Created, new
        {
            id = "WC-2",
            vin = doc.RootElement.GetProperty("vin").GetString(),
            status = "SUBMITTED",
            description = doc.RootElement.GetProperty("description").GetString(),
            submittedAt = "2026-03-01T09:00:00Z",
        });
    }

    private static HttpResponseMessage Respond(HttpStatusCode status, object payload) =>
        new(status)
        {
            Content = new StringContent(payload as string ?? JsonSerializer.Serialize(payload, Json), Encoding.UTF8, "application/json"),
        };
}
