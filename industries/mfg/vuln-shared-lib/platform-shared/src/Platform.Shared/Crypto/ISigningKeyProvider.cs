namespace Platform.Shared.Crypto;

/// <summary>Supplies the HMAC key used by <see cref="TokenSigner"/>.</summary>
public interface ISigningKeyProvider
{
    byte[] CurrentKey { get; }
}
