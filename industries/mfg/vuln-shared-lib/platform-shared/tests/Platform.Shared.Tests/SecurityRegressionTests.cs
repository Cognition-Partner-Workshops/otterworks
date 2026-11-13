using Platform.Shared.Crypto;
using Platform.Shared.Http;

namespace Platform.Shared.Tests;

#pragma warning disable CS0618
[Collection(SafeHttpCollection.Name)]
public class SecurityRegressionTests
{
    [Fact]
    public void LegacySigning_UsesSha256Length()
    {
        Assert.Equal(32, Base64Url.Decode(TokenSigner.Sign("vsl-synthetic-payload")).Length);
    }

    [Fact]
    public async Task LegacyFetch_DeniesWithoutDefault()
    {
        Environment.SetEnvironmentVariable("PLATFORM_SHARED_FETCH_ALLOWED_HOSTS", null);
        var stub = new StubHandler(_ => StubHandler.Ok("blocked"));
        SafeHttp.UseHandler(stub);
        await Assert.ThrowsAnyAsync<HttpRequestException>(() => SafeHttp.Fetch("https://blocked.example/"));
        Assert.Empty(stub.Requests);
    }
}
#pragma warning restore CS0618
