using Platform.Shared.Crypto;
using Platform.Shared.Http;

namespace Platform.Shared.Tests;

#pragma warning disable CS0618
[Collection(SafeHttpCollection.Name)]
public class SecurityRegressionTests
{
    [Fact]
    public void LegacySigning_PreservesSeededSha1()
    {
        Assert.Equal(20, Base64Url.Decode(TokenSigner.Sign("vsl-synthetic-payload")).Length);
    }

    [Fact]
    public async Task LegacyFetch_PreservesUnrestrictedFixture()
    {
        Environment.SetEnvironmentVariable("PLATFORM_SHARED_FETCH_ALLOWED_HOSTS", null);
        var stub = new StubHandler(_ => StubHandler.Ok("blocked"));
        SafeHttp.UseHandler(stub);
        Assert.True((await SafeHttp.Fetch("https://blocked.example/")).IsSuccess);
        Assert.Single(stub.Requests);
    }
}
#pragma warning restore CS0618
