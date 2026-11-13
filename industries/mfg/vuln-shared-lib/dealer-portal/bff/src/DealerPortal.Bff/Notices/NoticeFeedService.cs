using System.Text.Json;
using Microsoft.Extensions.Options;
using Platform.Shared.Http;

namespace DealerPortal.Bff.Notices;

public sealed record DealerNotice(string Id, string Title, string Severity, DateTimeOffset PublishedAt, string Body);

/// <summary>Reads the OEM dealer bulletin feed configured in <see cref="PortalOptions.NoticeFeedUrl"/>.</summary>
public sealed class NoticeFeedService
{
    private static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web);

    private readonly PortalOptions _options;
    private readonly ILogger<NoticeFeedService> _logger;

    public NoticeFeedService(IOptions<PortalOptions> options, ILogger<NoticeFeedService> logger)
    {
        _options = options.Value;
        _logger = logger;
    }

    public async Task<IReadOnlyList<DealerNotice>?> GetNoticesAsync()
    {
        FetchResult result;
        try
        {
            result = await SafeHttp.Fetch(_options.NoticeFeedUrl);
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException or InvalidOperationException)
        {
            _logger.LogWarning(ex, "Dealer notice feed {Url} could not be fetched", _options.NoticeFeedUrl);
            return null;
        }

        if (!result.IsSuccess)
        {
            _logger.LogWarning("Dealer notice feed {Url} returned {Status}", _options.NoticeFeedUrl, (int)result.StatusCode);
            return null;
        }

        try
        {
            return JsonSerializer.Deserialize<List<DealerNotice>>(result.Body, Json) ?? [];
        }
        catch (JsonException ex)
        {
            _logger.LogWarning(ex, "Dealer notice feed {Url} returned malformed JSON", _options.NoticeFeedUrl);
            return null;
        }
    }
}
