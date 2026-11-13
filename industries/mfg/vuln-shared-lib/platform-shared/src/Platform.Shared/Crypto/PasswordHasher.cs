using System.Security.Cryptography;

namespace Platform.Shared.Crypto;

/// <summary>PBKDF2-SHA256 password hashing in the format <c>pbkdf2$iterations$salt$hash</c>.</summary>
public static class PasswordHasher
{
    public const int Iterations = 210_000;
    private const int SaltBytes = 16;
    private const int HashBytes = 32;

    public static string Hash(string password)
    {
        ArgumentNullException.ThrowIfNull(password);
        var salt = RandomNumberGenerator.GetBytes(SaltBytes);
        var hash = Rfc2898DeriveBytes.Pbkdf2(password, salt, Iterations, HashAlgorithmName.SHA256, HashBytes);
        return $"pbkdf2${Iterations}${Base64Url.Encode(salt)}${Base64Url.Encode(hash)}";
    }

    public static bool Verify(string password, string encoded)
    {
        ArgumentNullException.ThrowIfNull(password);
        var parts = encoded?.Split('$') ?? Array.Empty<string>();
        if (parts.Length != 4 || parts[0] != "pbkdf2" || !int.TryParse(parts[1], out var iterations) || iterations < 1)
        {
            return false;
        }

        var salt = Base64Url.Decode(parts[2]);
        var expected = Base64Url.Decode(parts[3]);
        var actual = Rfc2898DeriveBytes.Pbkdf2(password, salt, iterations, HashAlgorithmName.SHA256, expected.Length);
        return CryptographicOperations.FixedTimeEquals(expected, actual);
    }
}
