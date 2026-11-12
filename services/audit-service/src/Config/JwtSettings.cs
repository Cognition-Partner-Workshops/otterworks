using System.Text;
using Microsoft.IdentityModel.Tokens;

namespace OtterWorks.AuditService.Config;

/// <summary>
/// Shared-secret JWT settings. The secret is the same HS256 key auth-service signs with
/// and the api-gateway verifies with, so audit-service can verify the caller's identity
/// and roles itself instead of trusting forwarded headers.
/// </summary>
public sealed class JwtSettings
{
    public const string SecretEnvironmentVariable = "JWT_SECRET";

    public string Secret { get; init; } = string.Empty;

    public static JwtSettings FromConfiguration(IConfiguration configuration)
    {
        var secret = configuration[SecretEnvironmentVariable] ?? configuration["Jwt:Secret"];
        if (string.IsNullOrWhiteSpace(secret))
        {
            throw new InvalidOperationException(
                $"{SecretEnvironmentVariable} is not set; audit-service refuses to start without the shared JWT signing key.");
        }

        return new JwtSettings { Secret = secret };
    }

    public SymmetricSecurityKey SigningKey => new(Encoding.UTF8.GetBytes(Secret));
}
