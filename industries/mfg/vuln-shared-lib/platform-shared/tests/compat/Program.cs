using Platform.Shared.Crypto;
using Platform.Shared.Http;

const string payload = "vsl-synthetic-compat";
const string expected = "DT8y6tTXY-DXVtp48b5aWm_4rTc";
Console.WriteLine($"Runtime Platform.Shared version: {typeof(TokenSigner).Assembly.GetName().Version}");
var signature = TokenSigner.Sign(payload);
if (signature != expected || !TokenSigner.Verify(payload, signature)) throw new Exception("Seeded signature changed.");
Console.WriteLine("Legacy Sign/Verify match seeded deterministic output.");
var handler = new FixtureHandler();
SafeHttp.UseHandler(handler);
foreach (var host in new[] { "allowed.example", "other.example" })
{
    var result = await SafeHttp.Fetch($"https://{host}/");
    if (!result.IsSuccess) throw new Exception("Legacy fixture fetch failed.");
}
if (handler.Requests != 2) throw new Exception("Legacy fetch did not reach fixture.");
Console.WriteLine("Legacy Fetch resolves and preserves unrestricted fixture behavior.");
Console.WriteLine("Binary compatibility: PASS.");

sealed class FixtureHandler : HttpMessageHandler
{
    public int Requests { get; private set; }
    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        Requests++;
        return Task.FromResult(new HttpResponseMessage(System.Net.HttpStatusCode.OK) { Content = new StringContent("ok") });
    }
}
