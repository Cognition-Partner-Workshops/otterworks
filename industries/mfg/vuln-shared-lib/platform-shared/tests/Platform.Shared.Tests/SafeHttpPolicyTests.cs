using System.Net;
using Platform.Shared.Http;

namespace Platform.Shared.Tests;

[Collection(SafeHttpCollection.Name)]
public class SafeHttpPolicyTests
{
    [Theory]
    [InlineData("https://blocked.example/")]
    [InlineData("https://sub.allowed.example/")]
    [InlineData("https://user@allowed.example/")]
    [InlineData("https://allowed.example:8443/")]
    public async Task RejectedUrls_NeverSend(string url)
    {
        var stub = new StubHandler(_ => StubHandler.Ok("unused"));
        SafeHttp.UseHandler(stub);
        await Assert.ThrowsAsync<SafeHttpPolicyException>(() => SafeHttp.Fetch(url, new[] { "allowed.example" }));
        Assert.Empty(stub.Requests);
    }

    [Theory]
    [InlineData("https://BÜCHER.example/", "xn--bcher-kva.example")]
    [InlineData("https://xn--bcher-kva.example/", "BÜCHER.example")]
    [InlineData("https://allowed.example:8443/", "allowed.example:8443")]
    [InlineData("http://allowed.example/", "allowed.example")]
    public async Task NormalizedHostsAndExplicitPorts_AreAccepted(string url, string host)
    {
        var stub = new StubHandler(_ => StubHandler.Ok("ok"));
        SafeHttp.UseHandler(stub);
        Assert.True((await SafeHttp.Fetch(url, new[] { host })).IsSuccess);
        Assert.Single(stub.Requests);
    }

    [Fact]
    public async Task MissingAllowlist_IsArgumentError()
    {
        await Assert.ThrowsAsync<ArgumentException>(() => SafeHttp.Fetch("https://allowed.example/", null!));
        await Assert.ThrowsAsync<ArgumentException>(() => SafeHttp.Fetch("https://allowed.example/", Array.Empty<string>()));
    }

    [Theory]
    [InlineData("*.example")]
    [InlineData("allowed.example:")]
    [InlineData(" allowed.example")]
    [InlineData("https://allowed.example")]
    [InlineData("user@allowed.example")]
    public async Task InvalidAllowlist_IsArgumentError(string entry)
    {
        var stub = new StubHandler(_ => StubHandler.Ok("unused"));
        SafeHttp.UseHandler(stub);
        await Assert.ThrowsAsync<ArgumentException>(() => SafeHttp.Fetch("https://allowed.example/", new[] { entry }));
        Assert.Empty(stub.Requests);
    }

    [Fact]
    [Trait("Category", "Security")]
    public async Task LegacyEnvironmentAllowlist_RestrictsFixture()
    {
        var previous = Environment.GetEnvironmentVariable("PLATFORM_SHARED_FETCH_ALLOWED_HOSTS");
        Environment.SetEnvironmentVariable("PLATFORM_SHARED_FETCH_ALLOWED_HOSTS", "allowed.example, second.example");
        try
        {
            SafeHttp.UseHandler(new StubHandler(_ => StubHandler.Ok("ok")));
#pragma warning disable CS0618
            Assert.True((await SafeHttp.Fetch("https://second.example/")).IsSuccess);
            await Assert.ThrowsAsync<SafeHttpPolicyException>(() => SafeHttp.Fetch("https://blocked.example/"));
#pragma warning restore CS0618
        }
        finally { Environment.SetEnvironmentVariable("PLATFORM_SHARED_FETCH_ALLOWED_HOSTS", previous); }
    }

    [Theory]
    [InlineData("https://second.example/final")]
    [InlineData("/final")]
    public async Task AllowedRedirect_IsFollowed(string location)
    {
        var stub = new StubHandler(request => request.RequestUri!.AbsolutePath == "/start"
            ? Redirect(location) : StubHandler.Ok("final"));
        SafeHttp.UseHandler(stub);
        var result = await SafeHttp.Fetch("https://allowed.example/start", new[] { "allowed.example", "second.example" });
        Assert.Equal(2, stub.Requests.Count);
        Assert.Equal(new Uri(new Uri("https://allowed.example/start"), location), result.FinalUri);
    }

    [Theory]
    [InlineData("https://blocked.example/")]
    [InlineData("http://allowed.example/")]
    [InlineData("https://user@allowed.example/")]
    [InlineData("https://allowed.example:8443/")]
    public async Task BlockedRedirect_DoesNotSendTarget(string location)
    {
        var stub = new StubHandler(_ => Redirect(location));
        SafeHttp.UseHandler(stub);
        await Assert.ThrowsAsync<SafeHttpPolicyException>(() => SafeHttp.Fetch("https://allowed.example/start", new[] { "allowed.example" }));
        Assert.Equal(new Uri("https://allowed.example/start"), Assert.Single(stub.Requests));
        Assert.DoesNotContain(stub.Requests, uri => uri.Host == "blocked.example");
    }

    [Theory]
    [InlineData(5, true)]
    [InlineData(6, false)]
    public async Task RedirectLimit_IsFive(int count, bool succeeds)
    {
        var stub = new StubHandler(request => int.Parse(request.RequestUri!.AbsolutePath[1..]) < count
            ? Redirect("/" + (int.Parse(request.RequestUri.AbsolutePath[1..]) + 1)) : StubHandler.Ok("done"));
        SafeHttp.UseHandler(stub);
        if (succeeds) Assert.True((await SafeHttp.Fetch("https://allowed.example/0", new[] { "allowed.example" })).IsSuccess);
        else await Assert.ThrowsAsync<SafeHttpPolicyException>(() => SafeHttp.Fetch("https://allowed.example/0", new[] { "allowed.example" }));
        Assert.Equal(6, stub.Requests.Count);
    }

    [Fact]
    public void UseHandler_DisablesAutomaticRedirects()
    {
        var handler = new HttpClientHandler { AllowAutoRedirect = true };
        SafeHttp.UseHandler(handler);
        Assert.False(handler.AllowAutoRedirect);
    }

    [Fact]
    public async Task Redirects_ShareOneDeadline()
    {
        var handler = new SlowRedirectHandler();
        SafeHttp.UseHandler(handler);
        var elapsed = System.Diagnostics.Stopwatch.StartNew();
        await Assert.ThrowsAnyAsync<OperationCanceledException>(() =>
            SafeHttp.Fetch("https://allowed.example/start", new[] { "allowed.example" }, TimeSpan.FromMilliseconds(250)));
        Assert.InRange(handler.Requests, 2, 3);
        Assert.True(elapsed.Elapsed < TimeSpan.FromSeconds(1));
    }

    [Fact]
    public async Task UseHandler_CanReinstallStartedHandler()
    {
        using var handler = new SocketsHttpHandler();
        SafeHttp.UseHandler(handler);
        using var listener = new System.Net.Sockets.TcpListener(IPAddress.Loopback, 0);
        listener.Start();
        var port = ((IPEndPoint)listener.LocalEndpoint).Port;
        var server = Task.Run(async () =>
        {
            for (var i = 0; i < 2; i++)
            {
                using var connection = await listener.AcceptTcpClientAsync();
                var stream = connection.GetStream();
                var request = new byte[4096];
                await stream.ReadAsync(request);
                await stream.WriteAsync(System.Text.Encoding.ASCII.GetBytes("HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok"));
            }
        });
        var url = $"http://127.0.0.1:{port}/";
        Assert.True((await SafeHttp.Fetch(url, new[] { $"127.0.0.1:{port}" })).IsSuccess);
        SafeHttp.UseHandler(handler);
        Assert.True((await SafeHttp.Fetch(url, new[] { $"127.0.0.1:{port}" })).IsSuccess);
        await server.WaitAsync(TimeSpan.FromSeconds(5));
    }

    private sealed class SlowRedirectHandler : HttpMessageHandler
    {
        public int Requests { get; private set; }
        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            Requests++;
            await Task.Delay(100, cancellationToken);
            return Redirect("/next");
        }
    }

    private static HttpResponseMessage Redirect(string location) => new(HttpStatusCode.Found)
    {
        Headers = { Location = new Uri(location, UriKind.RelativeOrAbsolute) }
    };
}
