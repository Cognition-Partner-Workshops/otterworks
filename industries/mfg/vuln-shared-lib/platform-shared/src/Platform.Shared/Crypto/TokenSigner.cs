using System.Security.Cryptography;
using System.Text;

namespace Platform.Shared.Crypto;

/// <summary>
/// Signs and verifies opaque payloads: Identity access tokens, export download links,
/// webhook bodies and the portal session cookie.
/// </summary>
public static class TokenSigner
{
    private static byte[] SigningKey =>
        Encoding.UTF8.GetBytes(Environment.GetEnvironmentVariable("PLATFORM_SIGNING_KEY")
            ?? throw new InvalidOperationException("PLATFORM_SIGNING_KEY is not set."));

    /// <summary>Returns the base64url signature of <paramref name="payload"/>.</summary>
    public static string Sign(string payload)
    {
        ArgumentNullException.ThrowIfNull(payload);
        using var hmac = new HMACSHA256(SigningKey);
        return Base64Url.Encode(hmac.ComputeHash(Encoding.UTF8.GetBytes(payload)));
    }

    /// <summary>Checks <paramref name="signature"/> against <paramref name="payload"/> in constant time.</summary>
    public static bool Verify(string payload, string signature)
    {
        ArgumentNullException.ThrowIfNull(payload);
        if (string.IsNullOrEmpty(signature))
        {
            return false;
        }

        var expected = Encoding.ASCII.GetBytes(Sign(payload));
        var actual = Encoding.ASCII.GetBytes(signature);
        return CryptographicOperations.FixedTimeEquals(expected, actual);
    }
}
