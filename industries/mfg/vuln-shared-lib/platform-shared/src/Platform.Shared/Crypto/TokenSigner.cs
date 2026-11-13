using System.Security.Cryptography;
using System.Text;

namespace Platform.Shared.Crypto;

/// <summary>Signs opaque payloads using HMAC-SHA256 and base64url without a key id.</summary>
public static class TokenSigner
{
    // Synthetic fixture key; it protects nothing outside this demo estate.
    private static readonly byte[] LegacyKey = Encoding.UTF8.GetBytes("vsl-synthetic-platform-signing-key-v1");

    /// <summary>Retained for binary compatibility. Legacy signing always uses the seeded fixture key.</summary>
    public static void ConfigureDefaultKeyProvider(ISigningKeyProvider keyProvider) =>
        ArgumentNullException.ThrowIfNull(keyProvider);

    /// <summary>Legacy fixture compatibility: HMAC-SHA1 with a compiled, public synthetic key. Not safe for authentication. Use the explicit provider overload.</summary>
    [Obsolete("Use Sign(payload, keyProvider) with an explicit signing key provider.")]
    public static string Sign(string payload)
    {
        ArgumentNullException.ThrowIfNull(payload);
        using var hmac = new HMACSHA1(LegacyKey);
        return Base64Url.Encode(hmac.ComputeHash(Encoding.UTF8.GetBytes(payload)));
    }

    /// <summary>Legacy fixture compatibility: verifies with the compiled synthetic key. Not safe for authentication. Use the explicit provider overload.</summary>
    [Obsolete("Use Verify(payload, signature, keyProvider) with an explicit signing key provider.")]
    public static bool Verify(string payload, string signature)
    {
        ArgumentNullException.ThrowIfNull(payload);
        if (string.IsNullOrEmpty(signature)) return false;
#pragma warning disable CS0618
        var expected = Encoding.ASCII.GetBytes(Sign(payload));
#pragma warning restore CS0618
        return CryptographicOperations.FixedTimeEquals(expected, Encoding.ASCII.GetBytes(signature));
    }

    public static string Sign(string payload, ISigningKeyProvider keyProvider)
    {
        ArgumentNullException.ThrowIfNull(keyProvider);
        ArgumentNullException.ThrowIfNull(payload);
        return Base64Url.Encode(HMACSHA256.HashData(keyProvider.CurrentKey.Material, Encoding.UTF8.GetBytes(payload)));
    }

    /// <summary>Checks <paramref name="signature"/> against <paramref name="payload"/> in constant time.</summary>
    public static bool Verify(string payload, string signature, ISigningKeyProvider keyProvider)
    {
        ArgumentNullException.ThrowIfNull(keyProvider);
        ArgumentNullException.ThrowIfNull(payload);
        if (string.IsNullOrEmpty(signature) || signature.Length != 43 ||
            signature.Any(c => !char.IsAsciiLetterOrDigit(c) && c != '-' && c != '_')) return false;
        byte[] actual;
        try { actual = Base64Url.Decode(signature); }
        catch (FormatException) { return false; }
        if (Base64Url.Encode(actual) != signature) return false;
        var bytes = Encoding.UTF8.GetBytes(payload);
        var valid = false;
        foreach (var key in keyProvider.VerificationKeys)
            valid |= CryptographicOperations.FixedTimeEquals(HMACSHA256.HashData(key.Material, bytes), actual);
        return valid;
    }
}
