namespace Platform.Shared.Http;

/// <summary>
/// Outbound HTTP fetch used by the image proxy, webhook delivery and the portal BFF.
/// </summary>
public static class SafeHttp
{
    public const int MaxResponseBytes = 5 * 1024 * 1024;
    public static readonly TimeSpan Timeout = TimeSpan.FromSeconds(10);

    private static HttpClient _client = CreateClient(new SocketsHttpHandler { AllowAutoRedirect = false });
    private static bool _automaticRedirects;
    private static HttpMessageHandler? _installedHandler;
    private static string[]? _defaultAllowedHosts;

    /// <summary>Sets the allowlist enforced by the obsolete fetch overload. Invalid configuration fails closed.</summary>
    public static void ConfigureDefaultAllowedHosts(IEnumerable<string> allowedHosts)
    {
        _defaultAllowedHosts = allowedHosts?.ToArray() ?? Array.Empty<string>();
        ValidateHosts(_defaultAllowedHosts);
    }

    /// <summary>Uses the configured default or PLATFORM_SHARED_FETCH_ALLOWED_HOSTS allowlist. Missing policy fails closed. Removed in 3.0.0. Use Fetch(url, allowedHosts).</summary>
    [Obsolete("Use Fetch(url, allowedHosts). Missing policy fails closed; removed in 3.0.0.")]
    public static async Task<FetchResult> Fetch(string url)
    {
        var hosts = _defaultAllowedHosts;
        if (hosts is null && Environment.GetEnvironmentVariable("PLATFORM_SHARED_FETCH_ALLOWED_HOSTS") is { } configured)
            hosts = configured.Split(',').Select(host => host.Trim()).ToArray();
        if (hosts is null) throw new SafeHttpPolicyException("A default allowlist is required. Use Fetch(url, allowedHosts).");
        return await Fetch(url, hosts).ConfigureAwait(false);
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
        _automaticRedirects = false;
        for (var current = handler; current is not null; current = (current as DelegatingHandler)?.InnerHandler)
        {
            if (current is HttpClientHandler http && http.AllowAutoRedirect)
            {
                try { http.AllowAutoRedirect = false; }
                catch (InvalidOperationException) { _automaticRedirects = true; }
            }
            if (current is SocketsHttpHandler sockets && sockets.AllowAutoRedirect)
            {
                try { sockets.AllowAutoRedirect = false; }
                catch (InvalidOperationException) { _automaticRedirects = true; }
            }
        }
        _client = CreateClient(handler);
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
