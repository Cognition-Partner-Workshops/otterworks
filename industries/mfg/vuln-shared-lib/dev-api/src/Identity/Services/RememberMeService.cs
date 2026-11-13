using System.Security.Cryptography;
using System.Text;
using Platform.Shared.Crypto;

namespace Identity.Services;

public sealed class RememberMeService
{
    private readonly DataProtector protector = new(RandomNumberGenerator.GetBytes(32));

    public string Create(string email) =>
        Base64Url.Encode(protector.Protect(Encoding.UTF8.GetBytes(email)));

    public string Read(string cookie)
    {
        try
        {
            return Encoding.UTF8.GetString(protector.Unprotect(Base64Url.Decode(cookie)));
        }
        catch (Exception error) when (error is FormatException or CryptographicException)
        {
            throw new CryptographicException("Invalid remember-me cookie.", error);
        }
    }
}
