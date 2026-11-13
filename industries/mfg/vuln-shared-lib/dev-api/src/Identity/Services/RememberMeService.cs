using System.Security.Cryptography;
using System.Text;

namespace Identity.Services;

public sealed class RememberMeService
{
    private readonly byte[] key = RandomNumberGenerator.GetBytes(32);

    public string Create(string email)
    {
        using var aes = Aes.Create();
        aes.Key = key;
        aes.Mode = CipherMode.ECB;
        using var encryptor = aes.CreateEncryptor();
        var bytes = Encoding.UTF8.GetBytes(email);
        return Convert.ToBase64String(encryptor.TransformFinalBlock(bytes, 0, bytes.Length));
    }
}
