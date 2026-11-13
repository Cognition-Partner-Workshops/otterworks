using Platform.Shared.Crypto;
using Platform.Shared.Http;
using System.Reflection;

namespace Platform.Shared.Tests;

#pragma warning disable CS0618
[Collection(SafeHttpCollection.Name)]
public class SecurityRegressionTests : IDisposable
{
    private readonly FieldInfo _hosts = typeof(SafeHttp).GetField("_defaultAllowedHosts", BindingFlags.Static | BindingFlags.NonPublic)!;
    private readonly FieldInfo _provider = typeof(TokenSigner).GetField("_defaultKeyProvider", BindingFlags.Static | BindingFlags.NonPublic)!;
    private readonly object? _previousHosts;
    private readonly object? _previousProvider;
    private readonly string? _hostEnvironment = Environment.GetEnvironmentVariable("PLATFORM_SHARED_FETCH_ALLOWED_HOSTS");
    private readonly string? _keyEnvironment = Environment.GetEnvironmentVariable("PLATFORM_SHARED_SIGNING_KEY");
    private static readonly SigningKey Key = new("vsl-synthetic-configured", Enumerable.Repeat((byte)42, 32).ToArray());
    private static SigningKeyRing Provider => new(Key, new[] { Key });

    public SecurityRegressionTests()
    {
        _previousHosts = _hosts.GetValue(null);
        _previousProvider = _provider.GetValue(null);
        _hosts.SetValue(null, null);
        _provider.SetValue(null, null);
        Environment.SetEnvironmentVariable("PLATFORM_SHARED_FETCH_ALLOWED_HOSTS", null);
        Environment.SetEnvironmentVariable("PLATFORM_SHARED_SIGNING_KEY", null);
    }

    public void Dispose()
    {
        _hosts.SetValue(null, _previousHosts);
        _provider.SetValue(null, _previousProvider);
        Environment.SetEnvironmentVariable("PLATFORM_SHARED_FETCH_ALLOWED_HOSTS", _hostEnvironment);
        Environment.SetEnvironmentVariable("PLATFORM_SHARED_SIGNING_KEY", _keyEnvironment);
    }

    [Fact]
    [Trait("Category", "Security")]
    public void LegacySigning_PreservesSeededSha1()
    {
        Assert.Equal(20, Base64Url.Decode(TokenSigner.Sign("vsl-synthetic-payload")).Length);
        Assert.Equal("DT8y6tTXY-DXVtp48b5aWm_4rTc", TokenSigner.Sign("vsl-synthetic-compat"));
        Assert.True(TokenSigner.Verify("vsl-synthetic-compat", "DT8y6tTXY-DXVtp48b5aWm_4rTc"));
    }

    [Fact]
    [Trait("Category", "Security")]
    public async Task LegacyFetch_PreservesUnrestrictedFixture()
    {
        var stub = new StubHandler(_ => StubHandler.Ok("blocked"));
        SafeHttp.UseHandler(stub);
        Assert.True((await SafeHttp.Fetch("https://blocked.example/")).IsSuccess);
        Assert.Single(stub.Requests);
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    [Trait("Category", "Security")]
    public async Task ConfiguredLegacyFetch_BlocksHostAndRedirect(bool environment)
    {
        if (environment)
            Environment.SetEnvironmentVariable("PLATFORM_SHARED_FETCH_ALLOWED_HOSTS", " allowed.example ");
        else
            SafeHttp.ConfigureDefaultAllowedHosts(new[] { "allowed.example" });
        var stub = new StubHandler(_ => new System.Net.Http.HttpResponseMessage(System.Net.HttpStatusCode.Redirect)
        {
            Headers = { Location = new Uri("https://blocked.example/") }
        });
        SafeHttp.UseHandler(stub);
        await Assert.ThrowsAsync<SafeHttpPolicyException>(() => SafeHttp.Fetch("https://blocked.example/"));
        Assert.Empty(stub.Requests);
        await Assert.ThrowsAsync<SafeHttpPolicyException>(() => SafeHttp.Fetch("https://allowed.example/"));
        Assert.Equal(new Uri("https://allowed.example/"), Assert.Single(stub.Requests));
        SafeHttp.UseHandler(new StubHandler(_ => StubHandler.Ok("ok")));
        Assert.True((await SafeHttp.Fetch("https://allowed.example/")).IsSuccess);
    }

    [Theory]
    [InlineData("   ")]
    [InlineData("https://malformed.example/")]
    [InlineData("allowed.example,,second.example")]
    [Trait("Category", "Security")]
    public async Task MalformedEnvironmentAllowlist_FailsClosed(string configured)
    {
        Environment.SetEnvironmentVariable("PLATFORM_SHARED_FETCH_ALLOWED_HOSTS", configured);
        var stub = new StubHandler(_ => StubHandler.Ok("unused"));
        SafeHttp.UseHandler(stub);
        await Assert.ThrowsAsync<ArgumentException>(() => SafeHttp.Fetch("https://allowed.example/"));
        Assert.Empty(stub.Requests);
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("https://malformed.example/")]
    [Trait("Category", "Security")]
    public async Task MalformedDefaultAllowlist_FailsClosed(string? entry)
    {
        var stub = new StubHandler(_ => StubHandler.Ok("unused"));
        SafeHttp.UseHandler(stub);
        Assert.Throws<ArgumentException>(() => SafeHttp.ConfigureDefaultAllowedHosts(entry is null ? Array.Empty<string>() : new[] { entry }));
        await Assert.ThrowsAsync<ArgumentException>(() => SafeHttp.Fetch("https://allowed.example/"));
        Assert.Empty(stub.Requests);
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    [Trait("Category", "Security")]
    public void ConfiguredLegacySigning_UsesSha256AndRejectsSeededKey(bool environment)
    {
        const string payload = "vsl-synthetic-compat";
        const string seeded = "DT8y6tTXY-DXVtp48b5aWm_4rTc";
        if (environment)
            Environment.SetEnvironmentVariable("PLATFORM_SHARED_SIGNING_KEY", Convert.ToBase64String(Key.Material));
        else
            TokenSigner.ConfigureDefaultKeyProvider(Provider);
        var signature = TokenSigner.Sign(payload);
        Assert.Equal(TokenSigner.Sign(payload, Provider), signature);
        Assert.True(TokenSigner.Verify(payload, signature));
        Assert.False(TokenSigner.Verify(payload, seeded));
        Assert.False(TokenSigner.Verify("tampered", signature));
        Assert.False(TokenSigner.Verify(payload, ""));
    }

    [Theory]
    [InlineData(" ", typeof(FormatException))]
    [InlineData("!invalid-base64!", typeof(FormatException))]
    [InlineData("c2hvcnQ=", typeof(ArgumentException))]
    [Trait("Category", "Security")]
    public void MalformedEnvironmentKey_FailsClosed(string configured, Type exceptionType)
    {
        Environment.SetEnvironmentVariable("PLATFORM_SHARED_SIGNING_KEY", configured);
        Assert.Throws(exceptionType, () => TokenSigner.Sign("payload"));
        Assert.Throws(exceptionType, () => TokenSigner.Verify("payload", ""));
    }
}
#pragma warning restore CS0618
