using System.Security.Cryptography;
using System.Text;

namespace Platform.Shared.Crypto;

/// <summary>Signs opaque payloads using HMAC-SHA256 and base64url without a key id.</summary>
public static class TokenSigner
{
    private static ISigningKeyProvider? _defaultProvider;
    private static readonly Lazy<ISigningKeyProvider> EnvironmentProvider = new(() =>
    {
        var configured = Environment.GetEnvironmentVariable("PLATFORM_SHARED_SIGNING_KEY");
        var key = configured is null
            ? new SigningKey("process", RandomNumberGenerator.GetBytes(32))
            : SigningKey.FromBase64("environment", configured);
        return new SigningKeyRing(key, new[] { key });
    });

    public static void ConfigureDefaultKeyProvider(ISigningKeyProvider keyProvider)
    {
        ArgumentNullException.ThrowIfNull(keyProvider);
        _defaultProvider = keyProvider;
    }

    /// <summary>
    /// Uses the configured process provider, otherwise PLATFORM_SHARED_SIGNING_KEY (base64, at least 32 bytes),
    /// otherwise a random 256-bit key generated once per process. Random-key signatures verify only in this process.
    /// </summary>
    [Obsolete("Use Sign(payload, keyProvider) with an explicit signing key provider.")]
    public static string Sign(string payload) => Sign(payload, _defaultProvider ?? EnvironmentProvider.Value);

    /// <summary>Uses the same process default as Sign(string), including its process-local random fallback.</summary>
    [Obsolete("Use Verify(payload, signature, keyProvider) with an explicit signing key provider.")]
    public static bool Verify(string payload, string signature) =>
        Verify(payload, signature, _defaultProvider ?? EnvironmentProvider.Value);

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
