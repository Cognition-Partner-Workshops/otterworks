using System.Security.Cryptography;

namespace Platform.Shared.Crypto;

public sealed class SigningKey
{
    private readonly byte[] _material;
    public string Id { get; }
    public byte[] Material => (byte[])_material.Clone();

    public SigningKey(string id, byte[] material)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(id);
        ArgumentNullException.ThrowIfNull(material);
        if (material.Length < 32) throw new ArgumentException("Signing keys must contain at least 32 bytes.", nameof(material));
        Id = id;
        _material = (byte[])material.Clone();
    }

    /// <summary>Accepts base64 or unpadded base64url key material.</summary>
    public static SigningKey FromBase64(string id, string material) => new(id, Base64Url.Decode(material));
}

public interface ISigningKeyProvider
{
    SigningKey CurrentKey { get; }
    IEnumerable<SigningKey> VerificationKeys { get; }
}

public sealed class SigningKeyRing : ISigningKeyProvider
{
    public SigningKey CurrentKey { get; }
    public IEnumerable<SigningKey> VerificationKeys { get; }

    public SigningKeyRing(SigningKey currentKey, IEnumerable<SigningKey> verificationKeys)
    {
        ArgumentNullException.ThrowIfNull(currentKey);
        ArgumentNullException.ThrowIfNull(verificationKeys);
        var keys = verificationKeys.ToArray();
        if (keys.Length == 0 || keys.Any(key => key is null))
            throw new ArgumentException("Verification keys must be nonempty and contain no nulls.", nameof(verificationKeys));
        CurrentKey = currentKey;
        var unique = new Dictionary<string, SigningKey>(StringComparer.Ordinal);
        var ordered = new List<SigningKey>();
        foreach (var key in new[] { currentKey }.Concat(keys))
        {
            if (unique.TryGetValue(key.Id, out var existing))
            {
                if (!CryptographicOperations.FixedTimeEquals(existing.Material, key.Material))
                    throw new ArgumentException("Signing keys with the same id must not have different material.", nameof(verificationKeys));
            }
            else
            {
                unique.Add(key.Id, key);
                ordered.Add(key);
            }
        }
        VerificationKeys = Array.AsReadOnly(ordered.ToArray());
    }
}
