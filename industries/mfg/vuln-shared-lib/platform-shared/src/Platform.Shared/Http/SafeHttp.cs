namespace Platform.Shared.Http;

/// <summary>
/// Outbound HTTP fetch used by the image proxy, webhook delivery and the portal BFF.
/// </summary>
public static class SafeHttp
{
    public const int MaxResponseBytes = 5 * 1024 * 1024;
    public static readonly TimeSpan Timeout = TimeSpan.FromSeconds(10);

    private static HttpClient _client = CreateClient(new SocketsHttpHandler { AllowAutoRedirect = false });

    /// <summary>Fetches <paramref name="url"/> when its host is in <paramref name="allowedHosts"/>.</summary>
    public static async Task<FetchResult> Fetch(string url, IReadOnlySet<string> allowedHosts)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(url);
        ArgumentNullException.ThrowIfNull(allowedHosts);
        if (!Uri.TryCreate(url, UriKind.Absolute, out var uri) ||
            (uri.Scheme != Uri.UriSchemeHttp && uri.Scheme != Uri.UriSchemeHttps))
        {
            throw new ArgumentException($"Only absolute http(s) URLs can be fetched: '{url}'.", nameof(url));
        }

        if (!allowedHosts.Contains(uri.Host))
        {
            throw new ArgumentException($"Host '{uri.Host}' is not allowed.", nameof(url));
        }

        using var response = await _client.GetAsync(uri, HttpCompletionOption.ResponseHeadersRead).ConfigureAwait(false);
        var body = await ReadBounded(response.Content).ConfigureAwait(false);
        return new FetchResult(
            response.StatusCode,
            response.Content.Headers.ContentType?.MediaType,
            body,
            response.RequestMessage?.RequestUri ?? uri);
    }

    /// <summary>Replaces the transport, for tests and local fixtures.</summary>
    public static void UseHandler(HttpMessageHandler handler)
    {
        ArgumentNullException.ThrowIfNull(handler);
        _client = CreateClient(handler);
    }

    private static HttpClient CreateClient(HttpMessageHandler handler) =>
        new(handler, disposeHandler: false) { Timeout = Timeout };

    private static async Task<byte[]> ReadBounded(HttpContent content)
    {
        await using var stream = await content.ReadAsStreamAsync().ConfigureAwait(false);
        using var buffer = new MemoryStream();
        var chunk = new byte[81920];
        int read;
        while ((read = await stream.ReadAsync(chunk).ConfigureAwait(false)) > 0)
        {
            if (buffer.Length + read > MaxResponseBytes)
            {
                throw new InvalidOperationException($"Response exceeds {MaxResponseBytes} bytes.");
            }

            buffer.Write(chunk, 0, read);
        }

        return buffer.ToArray();
    }
}
