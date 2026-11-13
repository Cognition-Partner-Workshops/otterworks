using System.Net.Http.Json;
using DealerPortal.Bff.Upstream;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.DependencyInjection;
using Platform.Shared.Http;

namespace DealerPortal.Bff.Tests;

[CollectionDefinition(Name)]
public sealed class BffCollection
{
    // SafeHttp's transport is process-wide, so tests that swap it must not run in parallel.
    public const string Name = "bff";
}

public sealed class PortalFactory : WebApplicationFactory<Program>
{
    private readonly Dictionary<string, string?> _settings;

    public PortalFactory(Dictionary<string, string?>? settings = null)
    {
        _settings = new Dictionary<string, string?>
        {
            ["Portal:DevApiBaseUrl"] = "http://dev-api.test",
            ["Portal:NoticeFeedUrl"] = "https://bulletins.oem.example/dealer-notices.json",
            ["Portal:SecureCookie"] = "true",
            ["Portal:StaticRoot"] = Path.Combine(Path.GetTempPath(), "dp-missing-" + Guid.NewGuid()),
        };
        foreach (var (key, value) in settings ?? [])
        {
            _settings[key] = value;
        }

        SafeHttp.UseHandler(Upstream);
    }

    public StubUpstream Upstream { get; } = new();

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        foreach (var (key, value) in _settings)
        {
            builder.UseSetting(key, value);
        }

        builder.ConfigureTestServices(services =>
            services.AddHttpClient<DevApiClient>().ConfigurePrimaryHttpMessageHandler(() => Upstream));
    }

    /// <summary>Client that has signed in and carries the session cookie on every request.</summary>
    public async Task<HttpClient> SignedInClientAsync()
    {
        var client = CreateClient(new WebApplicationFactoryClientOptions { HandleCookies = false });
        var response = await client.PostAsJsonAsync("/bff/session", new { email = StubUpstream.Email, password = "vsl-synthetic-portal-pass" });
        response.EnsureSuccessStatusCode();
        var cookie = response.Headers.GetValues("Set-Cookie").Single().Split(';')[0];
        client.DefaultRequestHeaders.Add("Cookie", cookie);
        return client;
    }
}
