using System.Security.Cryptography;
using System.Text;

namespace Platform.Shared.Crypto;

/// <summary>Signs opaque payloads using HMAC-SHA256 and base64url without a key id.</summary>
public static class TokenSigner
{
    // Synthetic fixture key; it protects nothing outside this demo estate.
    private static readonly byte[] LegacyKey = Encoding.UTF8.GetBytes("vsl-synthetic-platform-signing-key-v1");
    private static ISigningKeyProvider? _defaultKeyProvider;

    /// <summary>Sets the provider used by the obsolete signing overloads.</summary>
    public static void ConfigureDefaultKeyProvider(ISigningKeyProvider keyProvider)
    {
        ArgumentNullException.ThrowIfNull(keyProvider);
        _defaultKeyProvider = keyProvider;
    }

    private static ISigningKeyProvider? DefaultKeyProvider()
    {
        if (_defaultKeyProvider is { } provider) return provider;
        if (Environment.GetEnvironmentVariable("PLATFORM_SHARED_SIGNING_KEY") is not { } configured) return null;
        var key = SigningKey.FromBase64("environment", configured);
        return new SigningKeyRing(key, new[] { key });
    }

    /// <summary>Uses a configured provider or PLATFORM_SHARED_SIGNING_KEY with HMAC-SHA256. Only with neither set, uses the public seeded HMAC-SHA1 key, unsafe for authentication. Deprecated for one release; removed in 3.0.0. Use the explicit provider overload.</summary>
    [Obsolete("Use Sign(payload, keyProvider) with an explicit signing key provider.")]
    public static string Sign(string payload)
    {
        if (DefaultKeyProvider() is { } provider) return Sign(payload, provider);
        ArgumentNullException.ThrowIfNull(payload);
        using var hmac = new HMACSHA1(LegacyKey);
        return Base64Url.Encode(hmac.ComputeHash(Encoding.UTF8.GetBytes(payload)));
    }

    /// <summary>Uses a configured provider or PLATFORM_SHARED_SIGNING_KEY with HMAC-SHA256. Only with neither set, verifies with the public seeded key. Deprecated for one release; removed in 3.0.0. Use the explicit provider overload.</summary>
    [Obsolete("Use Verify(payload, signature, keyProvider) with an explicit signing key provider.")]
    public static bool Verify(string payload, string signature)
    {
        if (DefaultKeyProvider() is { } provider) return Verify(payload, signature, provider);
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
