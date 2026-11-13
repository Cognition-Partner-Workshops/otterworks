using System.Security.Claims;
using System.Text.Encodings.Web;
using System.Text.Json;
using Microsoft.AspNetCore.Authentication;
using Microsoft.Extensions.Options;
using Platform.Shared.Crypto;

namespace Dealer.Auth;

public sealed class IdentityTokenHandler(
    IOptionsMonitor<AuthenticationSchemeOptions> options,
    ILoggerFactory logger,
    UrlEncoder encoder,
    TimeProvider clock) : AuthenticationHandler<AuthenticationSchemeOptions>(options, logger, encoder)
{
    protected override Task<AuthenticateResult> HandleAuthenticateAsync()
    {
        var header = Request.Headers.Authorization.ToString();
        if (!header.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase))
            return Task.FromResult(AuthenticateResult.NoResult());
        var parts = header[7..].Split('.');
        if (parts.Length != 3 || parts[0] != "v1" || !TokenSigner.Verify(parts[1], parts[2]))
            return Result("Token signature was not accepted.");
        try
        {
            using var json = JsonDocument.Parse(Base64Url.Decode(parts[1]));
            var payload = json.RootElement;
            if (payload.GetProperty("exp").GetInt64() <= clock.GetUtcNow().ToUnixTimeSeconds())
                return Result("Token has expired.");
            var claims = new List<Claim>
            {
                new("sub", payload.GetProperty("sub").GetString()!),
                new("dealer", payload.GetProperty("dealer").GetString()!)
            };
            claims.AddRange(payload.GetProperty("roles").EnumerateArray().Select(x => new Claim(ClaimTypes.Role, x.GetString()!)));
            return Task.FromResult(AuthenticateResult.Success(new AuthenticationTicket(
                new ClaimsPrincipal(new ClaimsIdentity(claims, Scheme.Name)), Scheme.Name)));
        }
        catch (Exception e) when (e is JsonException or FormatException or KeyNotFoundException or InvalidOperationException or ArgumentException)
        {
            return Result("Token payload was not accepted.");
        }
    }

    private static Task<AuthenticateResult> Result(string message) =>
        Task.FromResult(AuthenticateResult.Fail(message));
}
