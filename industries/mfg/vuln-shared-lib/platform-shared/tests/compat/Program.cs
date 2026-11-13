using Platform.Shared.Crypto;
using Platform.Shared.Http;
using System.Security.Cryptography;

const string payload = "vsl-synthetic-compat";
const string expected = "DT8y6tTXY-DXVtp48b5aWm_4rTc";
var assembly = typeof(TokenSigner).Assembly;
Console.WriteLine($"Runtime Platform.Shared AssemblyName: {assembly.GetName()}");
Console.WriteLine($"Runtime Platform.Shared path: {assembly.Location}");
Console.WriteLine($"Runtime Platform.Shared SHA-256: {Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(assembly.Location))).ToLowerInvariant()}");
var handler = new FixtureHandler();
SafeHttp.UseHandler(handler);
if (args.Contains("--seeded"))
{
    var signature = TokenSigner.Sign(payload);
    if (signature != expected || !TokenSigner.Verify(payload, signature)) throw new Exception("Seeded signature changed.");
    foreach (var host in new[] { "allowed.example", "other.example" })
        if (!(await SafeHttp.Fetch($"https://{host}/")).IsSuccess) throw new Exception("Seeded fetch failed.");
    if (handler.Requests != 2) throw new Exception("Seeded fetch did not reach fixture.");
    Console.WriteLine("Seeded 1.0.0 baseline: PASS.");
}
else
{
    try { TokenSigner.Sign(payload); throw new Exception("Missing key did not deny signing."); }
    catch (InvalidOperationException) { Console.WriteLine("Legacy Sign binds and denies without a key."); }
    try { TokenSigner.Verify(payload, expected); throw new Exception("Missing key did not deny verification."); }
    catch (InvalidOperationException) { Console.WriteLine("Legacy Verify binds and denies without a key."); }
    try { await SafeHttp.Fetch("https://allowed.example/"); throw new Exception("Missing allowlist did not deny fetching."); }
    catch (HttpRequestException) { Console.WriteLine("Legacy Fetch binds and denies without a policy."); }
    if (handler.Requests != 0) throw new Exception("Denied request reached fixture.");
    Environment.SetEnvironmentVariable("PLATFORM_SHARED_SIGNING_KEY", Convert.ToBase64String(Enumerable.Repeat((byte)42, 32).ToArray()));
    Environment.SetEnvironmentVariable("PLATFORM_SHARED_FETCH_ALLOWED_HOSTS", "allowed.example");
    try
    {
        var signature = TokenSigner.Sign(payload);
        if (signature.Length != 43 || !TokenSigner.Verify(payload, signature) || TokenSigner.Verify(payload, expected))
            throw new Exception("Configured legacy signing policy failed.");
        if (!(await SafeHttp.Fetch("https://allowed.example/")).IsSuccess) throw new Exception("Allowed fixture fetch failed.");
        try { await SafeHttp.Fetch("https://other.example/"); throw new Exception("Blocked host was allowed."); }
        catch (HttpRequestException) { }
        if (handler.Requests != 1) throw new Exception("Blocked request reached fixture.");
        Console.WriteLine("Configured legacy overloads enforce HMAC-SHA256 and host policy.");
    }
    finally
    {
        Environment.SetEnvironmentVariable("PLATFORM_SHARED_SIGNING_KEY", null);
        Environment.SetEnvironmentVariable("PLATFORM_SHARED_FETCH_ALLOWED_HOSTS", null);
    }
}
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
