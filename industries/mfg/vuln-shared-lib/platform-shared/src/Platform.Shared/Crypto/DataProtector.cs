using System.Security.Cryptography;

namespace Platform.Shared.Crypto;

/// <summary>AES-256-GCM authenticated encryption. Output is <c>nonce || tag || ciphertext</c>.</summary>
public sealed class DataProtector
{
    private const int NonceBytes = 12;
    private const int TagBytes = 16;
    private readonly byte[] _key;

    public DataProtector(byte[] key)
    {
        ArgumentNullException.ThrowIfNull(key);
        if (key.Length != 32)
        {
            throw new ArgumentException("AES-256-GCM needs a 32-byte key.", nameof(key));
        }

        _key = (byte[])key.Clone();
    }

    public byte[] Protect(byte[] plaintext)
    {
        ArgumentNullException.ThrowIfNull(plaintext);
        var output = new byte[NonceBytes + TagBytes + plaintext.Length];
        var nonce = output.AsSpan(0, NonceBytes);
        RandomNumberGenerator.Fill(nonce);
        using var aes = new AesGcm(_key, TagBytes);
        aes.Encrypt(nonce, plaintext, output.AsSpan(NonceBytes + TagBytes), output.AsSpan(NonceBytes, TagBytes));
        return output;
    }

    public byte[] Unprotect(byte[] protectedData)
    {
        ArgumentNullException.ThrowIfNull(protectedData);
        if (protectedData.Length < NonceBytes + TagBytes)
        {
            throw new CryptographicException("Protected payload is too short.");
        }

        var plaintext = new byte[protectedData.Length - NonceBytes - TagBytes];
        using var aes = new AesGcm(_key, TagBytes);
        aes.Decrypt(
            protectedData.AsSpan(0, NonceBytes),
            protectedData.AsSpan(NonceBytes + TagBytes),
            protectedData.AsSpan(NonceBytes, TagBytes),
            plaintext);
        return plaintext;
    }
}
