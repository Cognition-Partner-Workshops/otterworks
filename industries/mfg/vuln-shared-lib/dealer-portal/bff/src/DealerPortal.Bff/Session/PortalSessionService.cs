using System.Text.Json;
using Microsoft.Extensions.Options;
using Platform.Shared.Crypto;

namespace DealerPortal.Bff.Session;

/// <summary>
/// Issues and reads the portal session cookie: base64url(session JSON) "." signature.
/// </summary>
public sealed class PortalSessionService
{
    public const string CookieName = "dp_session";

    private readonly TimeProvider _clock;
    private readonly ISigningKeyProvider _signingKeys;
    private readonly PortalOptions _options;

    public PortalSessionService(TimeProvider clock, IOptions<PortalOptions> options, ISigningKeyProvider signingKeys)
    {
        _clock = clock;
        _signingKeys = signingKeys;
        _options = options.Value;
    }

    public PortalSession Create(string email, string dealerId, string accessToken, int expiresInSeconds) =>
        new(email, dealerId, accessToken, _clock.GetUtcNow().AddSeconds(expiresInSeconds).ToUnixTimeSeconds());

    public string Encode(PortalSession session)
    {
        var payload = Base64Url.Encode(JsonSerializer.SerializeToUtf8Bytes(session));
        return payload + "." + TokenSigner.Sign(payload, _signingKeys);
    }

    public PortalSession? Decode(string? cookie)
    {
        if (string.IsNullOrEmpty(cookie))
        {
            return null;
        }

        var dot = cookie.LastIndexOf('.');
        if (dot <= 0 || dot == cookie.Length - 1)
        {
            return null;
        }

        var payload = cookie[..dot];
        if (!TokenSigner.Verify(payload, cookie[(dot + 1)..], _signingKeys))
        {
            return null;
        }

        PortalSession? session;
        try
        {
            session = JsonSerializer.Deserialize<PortalSession>(Base64Url.Decode(payload));
        }
        catch (Exception ex) when (ex is JsonException or FormatException)
        {
            return null;
        }

        return session is not null && session.ExpiresAt > _clock.GetUtcNow() ? session : null;
    }

    public PortalSession? Read(HttpRequest request) => Decode(request.Cookies[CookieName]);

    public void Write(HttpResponse response, PortalSession session) =>
        response.Cookies.Append(CookieName, Encode(session), CookieOptions(session.ExpiresAt));

    public void Clear(HttpResponse response) =>
        response.Cookies.Delete(CookieName, CookieOptions(null));

    private CookieOptions CookieOptions(DateTimeOffset? expires) => new()
    {
        HttpOnly = true,
        Secure = _options.SecureCookie,
        SameSite = SameSiteMode.Strict,
        Path = "/",
        Expires = expires,
    };
}
