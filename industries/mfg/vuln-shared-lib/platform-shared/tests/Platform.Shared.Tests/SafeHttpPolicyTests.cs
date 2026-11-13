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
    public async Task LegacyEnvironmentAllowlist_IsUsed()
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
    public async Task LegacyConfiguredAllowlist_AlsoBlocksRedirects()
    {
#pragma warning disable CS0618
        SafeHttp.ConfigureDefaultAllowedHosts(new[] { "allowed.example" });
        try
        {
            SafeHttp.UseHandler(new StubHandler(_ => StubHandler.Ok("ok")));
            Assert.True((await SafeHttp.Fetch("https://allowed.example/")).IsSuccess);
            var stub = new StubHandler(_ => Redirect("https://blocked.example/"));
            SafeHttp.UseHandler(stub);
            await Assert.ThrowsAsync<SafeHttpPolicyException>(() => SafeHttp.Fetch("https://allowed.example/"));
            Assert.Single(stub.Requests);
        }
        finally
        {
            typeof(SafeHttp).GetField("_defaultAllowedHosts", System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.NonPublic)!.SetValue(null, null);
        }
#pragma warning restore CS0618
    }

    private static HttpResponseMessage Redirect(string location) => new(HttpStatusCode.Found)
    {
        Headers = { Location = new Uri(location, UriKind.RelativeOrAbsolute) }
    };
}
