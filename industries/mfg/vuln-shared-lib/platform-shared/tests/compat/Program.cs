using Platform.Shared.Crypto;
using Platform.Shared.Http;

const string payload = "vsl-synthetic-compat";
if (!TokenSigner.Verify(payload, TokenSigner.Sign(payload))) throw new Exception("Signing round trip failed.");
Console.WriteLine("Legacy Sign/Verify resolved and round trip succeeded.");
SafeHttp.UseHandler(new FixtureHandler());
try
{
    await SafeHttp.Fetch("https://allowed.example/");
    throw new Exception("Expected default deny.");
}
catch (HttpRequestException)
{
    Console.WriteLine("Legacy Fetch resolved and denied without a default allowlist.");
}
Console.WriteLine("Binary compatibility: PASS (compiled against 1.0.0, running with 2.0.0).");

sealed class FixtureHandler : HttpMessageHandler
{
    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken) =>
        throw new Exception("No request should be sent.");
}
