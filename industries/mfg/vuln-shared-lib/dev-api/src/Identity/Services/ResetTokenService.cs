using System.Security.Cryptography;
using System.Text;
using Platform.Shared.Crypto;

namespace Identity.Services;

public sealed class ResetTokenService
{
    private readonly DataProtector protector = new(RandomNumberGenerator.GetBytes(32));

    public byte[] Create(string email) =>
        protector.Protect(Encoding.UTF8.GetBytes(email + ":" + Guid.NewGuid().ToString("N")));

    public string Read(byte[] token) => Encoding.UTF8.GetString(protector.Unprotect(token));
}
