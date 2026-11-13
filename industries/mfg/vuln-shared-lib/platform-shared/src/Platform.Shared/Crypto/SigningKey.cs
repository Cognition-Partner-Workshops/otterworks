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
        VerificationKeys = Array.AsReadOnly(keys);
    }
}
