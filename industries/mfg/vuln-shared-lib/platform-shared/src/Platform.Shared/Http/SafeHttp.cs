namespace Platform.Shared.Http;

/// <summary>
/// Outbound HTTP fetch used by the image proxy, webhook delivery and the portal BFF.
/// </summary>
public static class SafeHttp
{
    public const int MaxResponseBytes = 5 * 1024 * 1024;
    public static readonly TimeSpan Timeout = TimeSpan.FromSeconds(10);

    private static HttpClient _client = CreateClient(new SocketsHttpHandler { AllowAutoRedirect = false });
    private static HttpClient _legacyClient = CreateClient(new SocketsHttpHandler { AllowAutoRedirect = true });
    private static bool _legacyRedirects;
    private static bool _automaticRedirects;
    private static HttpMessageHandler? _installedHandler;

    /// <summary>Retained for binary compatibility. Validates entries but does not restrict the legacy fixture overload.</summary>
    public static void ConfigureDefaultAllowedHosts(IEnumerable<string> allowedHosts) => ValidateHosts(allowedHosts);

    /// <summary>Legacy fixture compatibility: unrestricted HTTP fetch and redirects, with no host allowlist. Unsafe for untrusted URLs. Use Fetch(url, allowedHosts).</summary>
    [Obsolete("Use Fetch(url, allowedHosts) with an explicit allowlist.")]
    public static async Task<FetchResult> Fetch(string url)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(url);
        if (!Uri.TryCreate(url, UriKind.Absolute, out var uri) ||
            (uri.Scheme != Uri.UriSchemeHttp && uri.Scheme != Uri.UriSchemeHttps))
            throw new ArgumentException($"Only absolute http(s) URLs can be fetched: '{url}'.", nameof(url));
        var client = _legacyClient;
        for (var redirects = 0; ; redirects++)
        {
            using var response = await client.GetAsync(uri, HttpCompletionOption.ResponseHeadersRead).ConfigureAwait(false);
            if (_legacyRedirects && (int)response.StatusCode is 300 or 301 or 302 or 303 or 307 or 308 &&
                response.Headers.Location is { } location && Uri.TryCreate(uri, location, out var next) &&
                (next.Scheme == Uri.UriSchemeHttp || next.Scheme == Uri.UriSchemeHttps) &&
                !(uri.Scheme == Uri.UriSchemeHttps && next.Scheme == Uri.UriSchemeHttp))
            {
                if (redirects >= 50) throw new HttpRequestException("Redirect limit exceeded.");
                uri = next;
                continue;
            }
            var body = await ReadBounded(response.Content).ConfigureAwait(false);
            return new FetchResult(response.StatusCode, response.Content.Headers.ContentType?.MediaType,
                body, response.RequestMessage?.RequestUri ?? uri);
        }
    }

    /// <summary>Fetches a URL, allowing only exact normalized hosts and approved ports, including on redirects.</summary>
    public static Task<FetchResult> Fetch(string url, IEnumerable<string> allowedHosts) => Fetch(url, allowedHosts, Timeout);

    internal static async Task<FetchResult> Fetch(string url, IEnumerable<string> allowedHosts, TimeSpan timeout)
    {
        var hosts = ValidateHosts(allowedHosts);
        if (!Uri.TryCreate(url, UriKind.Absolute, out var uri))
            throw new SafeHttpPolicyException("Only absolute http(s) URLs can be fetched.");
        CheckUri(uri, hosts);
        if (_automaticRedirects)
            throw new SafeHttpPolicyException("The supplied started handler still enables automatic redirects. Supply a handler with AllowAutoRedirect=false.");
        var client = _client;
        using var deadline = new CancellationTokenSource(timeout);
        for (var redirects = 0; ; redirects++)
        {
            using var response = await client.GetAsync(uri, HttpCompletionOption.ResponseHeadersRead, deadline.Token).ConfigureAwait(false);
            if ((int)response.StatusCode is 301 or 302 or 303 or 307 or 308 && response.Headers.Location is { } location)
            {
                if (redirects >= 5)
                    throw new SafeHttpPolicyException("Redirect limit exceeded.");
                if (!Uri.TryCreate(uri, location, out var next))
                    throw new SafeHttpPolicyException("Invalid redirect location.");
                CheckUri(next, hosts);
                if (uri.Scheme == Uri.UriSchemeHttps && next.Scheme == Uri.UriSchemeHttp)
                    throw new SafeHttpPolicyException("HTTPS downgrade rejected.");
                uri = next;
                continue;
            }
            var body = await ReadBounded(response.Content, deadline.Token).ConfigureAwait(false);
            return new FetchResult(response.StatusCode, response.Content.Headers.ContentType?.MediaType, body, uri);
        }
    }

    private static string[] ValidateHosts(IEnumerable<string> allowedHosts)
    {
        if (allowedHosts is null) throw new ArgumentException("An allowlist is required.", nameof(allowedHosts));
        var hosts = allowedHosts.ToArray();
        if (hosts.Length == 0) throw new ArgumentException("An allowlist is required.", nameof(allowedHosts));
        foreach (var host in hosts) ParseHost(host);
        return hosts;
    }

    private static (string Host, int? Port) ParseHost(string entry)
    {
        if (string.IsNullOrWhiteSpace(entry) || entry.Any(char.IsWhiteSpace) || entry.EndsWith(':') ||
            entry.IndexOfAny(new[] { '/', '@', '?', '#', '*', '\\' }) >= 0 ||
            !Uri.TryCreate("http://" + entry, UriKind.Absolute, out var parsed) || string.IsNullOrEmpty(parsed.Host))
            throw new ArgumentException("Allowlist entries must be host names or host:port.");
        var portSpecified = entry.StartsWith('[') ? entry.Contains("]:", StringComparison.Ordinal) : entry.Contains(':');
        return (parsed.IdnHost, portSpecified ? parsed.Port : null);
    }

    private static void CheckUri(Uri uri, string[] hosts)
    {
        if ((uri.Scheme != Uri.UriSchemeHttp && uri.Scheme != Uri.UriSchemeHttps) || uri.UserInfo.Length != 0)
            throw new SafeHttpPolicyException("Only http(s) URLs without userinfo are allowed.");
        if (!hosts.Select(ParseHost).Any(entry =>
            string.Equals(entry.Host, uri.IdnHost, StringComparison.OrdinalIgnoreCase) &&
            (entry.Port is { } port ? uri.Port == port : uri.IsDefaultPort)))
            throw new SafeHttpPolicyException("Host or port is not allowlisted.");
    }

    /// <summary>Replaces the transport, for tests and local fixtures.</summary>
    public static void UseHandler(HttpMessageHandler handler)
    {
        ArgumentNullException.ThrowIfNull(handler);
        if (ReferenceEquals(handler, _installedHandler)) return;
        _legacyRedirects = false;
        _automaticRedirects = false;
        for (var current = handler; current is not null; current = (current as DelegatingHandler)?.InnerHandler)
        {
            if (current is HttpClientHandler http && http.AllowAutoRedirect)
            {
                try { http.AllowAutoRedirect = false; _legacyRedirects = true; }
                catch (InvalidOperationException) { _automaticRedirects = true; }
            }
            if (current is SocketsHttpHandler sockets && sockets.AllowAutoRedirect)
            {
                try { sockets.AllowAutoRedirect = false; _legacyRedirects = true; }
                catch (InvalidOperationException) { _automaticRedirects = true; }
            }
        }
        _client = CreateClient(handler);
        _legacyClient = _client;
        _installedHandler = handler;
    }

    private static HttpClient CreateClient(HttpMessageHandler handler) =>
        new(handler, disposeHandler: false) { Timeout = Timeout };

    private static async Task<byte[]> ReadBounded(HttpContent content, CancellationToken cancellationToken = default)
    {
        await using var stream = await content.ReadAsStreamAsync(cancellationToken).ConfigureAwait(false);
        using var buffer = new MemoryStream();
        var chunk = new byte[81920];
        int read;
        while ((read = await stream.ReadAsync(chunk, cancellationToken).ConfigureAwait(false)) > 0)
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
