using Platform.Shared.Crypto;
using Platform.Shared.Http;

const string payload = "vsl-synthetic-compat";
if (!TokenSigner.Verify(payload, TokenSigner.Sign(payload))) throw new Exception("Signing round trip failed.");
Console.WriteLine("Legacy Sign/Verify resolved and round trip succeeded.");
var handler = new FixtureHandler();
SafeHttp.UseHandler(handler);
var configured = Environment.GetEnvironmentVariable("PLATFORM_SHARED_FETCH_ALLOWED_HOSTS") is not null;
if (configured)
{
    var result = await SafeHttp.Fetch("https://allowed.example/");
    if (!result.IsSuccess || handler.Requests != 1) throw new Exception("Expected allowed request.");
    Console.WriteLine("Legacy Fetch succeeded with configured allowed host.");
}
try
{
    await SafeHttp.Fetch(configured ? "https://blocked.example/" : "https://allowed.example/");
    throw new Exception("Expected policy rejection.");
}
catch (HttpRequestException)
{
    if (handler.Requests != (configured ? 1 : 0)) throw new Exception("Blocked request reached transport.");
    Console.WriteLine(configured ? "Legacy Fetch denied another host without sending." : "Legacy Fetch resolved and denied without a default allowlist.");
}
Console.WriteLine("Binary compatibility: PASS (compiled against 1.0.0, running with 2.0.0).");

sealed class FixtureHandler : HttpMessageHandler
{
    public int Requests { get; private set; }
    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        Requests++;
        if (request.RequestUri!.Host != "allowed.example") throw new Exception("Unexpected host.");
        return Task.FromResult(new HttpResponseMessage(System.Net.HttpStatusCode.OK) { Content = new StringContent("ok") });
    }
}
