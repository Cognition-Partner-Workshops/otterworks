using System.Security.Cryptography;
using System.Text;

namespace Platform.Shared.Crypto;

/// <summary>Signs opaque payloads using HMAC-SHA256 and base64url without a key id.</summary>
public static class TokenSigner
{
    private static ISigningKeyProvider? _defaultKeyProvider;

    /// <summary>Sets the provider used by the obsolete signing overloads.</summary>
    public static void ConfigureDefaultKeyProvider(ISigningKeyProvider keyProvider)
    {
        ArgumentNullException.ThrowIfNull(keyProvider);
        _defaultKeyProvider = keyProvider;
    }

    private static ISigningKeyProvider DefaultKeyProvider()
    {
        if (_defaultKeyProvider is { } provider) return provider;
        if (Environment.GetEnvironmentVariable("PLATFORM_SHARED_SIGNING_KEY") is not { } configured)
            throw new InvalidOperationException("A default signing key provider is required. Use the explicit provider overload.");
        var key = SigningKey.FromBase64("environment", configured);
        return new SigningKeyRing(key, new[] { key });
    }

    /// <summary>Uses a configured provider or PLATFORM_SHARED_SIGNING_KEY with HMAC-SHA256. Throws InvalidOperationException when no provider is configured. Removed in 3.0.0.</summary>
    [Obsolete("Use Sign(payload, keyProvider). Missing key policy fails closed; removed in 3.0.0.")]
    public static string Sign(string payload) => Sign(payload, DefaultKeyProvider());

    /// <summary>Uses a configured provider or PLATFORM_SHARED_SIGNING_KEY with HMAC-SHA256. Throws InvalidOperationException when no provider is configured, even for an empty signature. Removed in 3.0.0.</summary>
    [Obsolete("Use Verify(payload, signature, keyProvider). Missing key policy fails closed; removed in 3.0.0.")]
    public static bool Verify(string payload, string signature) => Verify(payload, signature, DefaultKeyProvider());

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
