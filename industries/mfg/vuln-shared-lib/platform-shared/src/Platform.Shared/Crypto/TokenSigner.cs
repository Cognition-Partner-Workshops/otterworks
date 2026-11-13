using System.Security.Cryptography;
using System.Text;

namespace Platform.Shared.Crypto;

/// <summary>
/// Signs and verifies opaque payloads: Identity access tokens, export download links,
/// webhook bodies and the portal session cookie.
/// </summary>
public static class TokenSigner
{
    /// <summary>Returns the base64url HMAC-SHA256 signature of <paramref name="payload"/>.</summary>
    public static string Sign(string payload, ISigningKeyProvider keys)
    {
        ArgumentNullException.ThrowIfNull(payload);
        ArgumentNullException.ThrowIfNull(keys);
        using var hmac = new HMACSHA256(keys.CurrentKey);
        return Base64Url.Encode(hmac.ComputeHash(Encoding.UTF8.GetBytes(payload)));
    }

    /// <summary>Checks <paramref name="signature"/> against <paramref name="payload"/> in constant time.</summary>
    public static bool Verify(string payload, string signature, ISigningKeyProvider keys)
    {
        ArgumentNullException.ThrowIfNull(payload);
        if (string.IsNullOrEmpty(signature))
        {
            return false;
        }

        var expected = Encoding.ASCII.GetBytes(Sign(payload, keys));
        var actual = Encoding.ASCII.GetBytes(signature);
        return CryptographicOperations.FixedTimeEquals(expected, actual);
    }
}
